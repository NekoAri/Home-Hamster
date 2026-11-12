"""
HomeHamster Agent 服务层（v4 - 主从 Agent 架构）

架构：
    用户 ⇄ 主 Agent（编排者，只持有委派工具）
              ├── 📒 记账子 Agent（只持有账目工具）
              └── 📦 库存子 Agent（只持有库存工具）

一次对话的流程：
1. 保存用户消息 → 加载滑动窗口上下文 → 构建 [主 Agent 系统提示 + 历史]
2. 流式请求主 Agent（带 delegate_to_* 委派工具），文字 token 实时下发给用户
3. 若主 Agent 决定派发：
   a. 记录 assistant 的 tool_calls 消息
   b. 通过 Orchestrator 并行执行子 Agent（asyncio.gather）
   c. 执行期间把子 Agent 状态事件（start/tool/done/error）实时推给前端，
      同时每 5 秒发一次 SSE 心跳，避免长任务被代理断连
   d. 把子 Agent 的结果聚合成 tool 消息回填上下文
4. 主 Agent 基于子 Agent 结论流式生成最终回复
5. 落库 + 视情况生成历史摘要

与 v3 的关键差异：
- 主 Agent 不再直接调用数据库工具，只负责理解、拆解、派发、汇总
- 子 Agent 拥有独立的 agent loop（多轮思考 + 工具），互不干扰
- 新增 agent_event 事件流，前端可展示"谁在干活"
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.services.agent_manager import AgentManager
from app.services.history_service import HistoryService
from app.services.llm_provider import StreamResult
from app.services.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# SSE 心跳（浏览器/代理会忽略以冒号开头的注释行，但连接保持活跃）
HEARTBEAT = ": heartbeat\n\n"

# 主 Agent 最多派发几轮（通常 1 轮就够；2 轮用于"先查再改"这类链式任务）
MAX_DELEGATE_ROUNDS = 2

# 派发执行期间，多久没事件就发一次心跳（秒）
DISPATCH_HEARTBEAT_SECONDS = 5.0


def _sse(payload: dict) -> str:
    """序列化为 SSE 数据帧"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _content_sse(token: str) -> str:
    """文本 token 帧"""
    return _sse({"content": token})


def _tool_calls_payload(tool_calls) -> list[dict]:
    """把 ToolCallResult 转成 DB/消息格式（OpenAI 风格）"""
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
            },
        }
        for tc in tool_calls
    ]


def _friendly_error(exc: Exception, provider) -> str:
    """把底层异常翻译成用户能看懂的提示"""
    error_str = str(exc)
    model_name = getattr(getattr(provider, "config", None), "model_name", "未知")

    if "502" in error_str or "Bad Gateway" in error_str:
        return "❌ LLM 服务器返回 502 Bad Gateway，服务未正常运行。\n请检查 LLM 服务是否已启动并加载模型。"
    if "Connection refused" in error_str or "ConnectError" in type(exc).__name__:
        return "❌ 无法连接到 LLM 服务器。\n请检查服务是否已启动、端口是否正确。"
    if "timeout" in error_str.lower() or "Timeout" in type(exc).__name__:
        return "❌ 请求超时，LLM 服务响应时间过长。\n本地模型推理可能较慢，请稍后重试或减小 max_tokens。"
    if "401" in error_str or "Unauthorized" in error_str or "api_key" in error_str.lower():
        return "❌ API Key 验证失败。\n请检查设置中的 API Key 是否正确。"
    if "404" in error_str or "not found" in error_str.lower() or "model" in error_str.lower():
        return f"❌ 模型不存在或路径错误: {model_name}\n请检查模型名称是否正确。"
    return f"❌ 模型调用失败: {error_str}\n请检查 LLM 配置（API Key、Base URL、模型名称等）。"


def _extract_conclusion(tool_message: dict) -> str:
    """从子 Agent 的 tool 消息里抽出结论段，用于兜底回复"""
    text = tool_message.get("content", "")
    marker = "返回结论:"
    if marker in text:
        body = text.split(marker, 1)[1]
        body = body.split("执行明细:", 1)[0]
        return body.strip().replace("\n", " ")
    return ""


async def chat_stream(
    session_id: str,
    content: str,
    user_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    主 Agent 对话流式处理（SSE 格式输出）

    事件类型：
    - 文本：{"content": "token"}
    - 子 Agent 状态：{"type": "agent_event", "event": "start|tool|done|error", ...}
    - 结束：data: [DONE]
    """
    # 立即发送心跳，建立 SSE 连接，防止代理超时
    yield HEARTBEAT

    # ---- 第 0 步：获取全局 Agent 实例 ----
    manager = AgentManager.get_instance()
    provider = await manager.get_provider()

    if provider is None:
        error_msg = (
            "⚠️ 尚未配置大模型。请在设置中添加 LLM 配置并激活。\n"
            "支持 OpenAI、Anthropic Claude、DeepSeek、智谱 GLM、本地 Ollama 等多种供应商。"
        )
        yield _content_sse(error_msg)
        yield "data: [DONE]\n\n"
        return

    system_prompt = manager.get_system_prompt()
    tools = orchestrator.get_tools()
    sub_providers = manager.get_sub_providers()  # 每个子 Agent 可绑定独立模型

    # ---- 第 1 步：保存用户消息到数据库 ----
    await HistoryService.save_message(
        session_id=session_id,
        role="user",
        content=content,
    )

    # ---- 第 2 步：加载上下文，构建主 Agent 消息 ----
    context_messages = await HistoryService.get_context_messages(session_id)
    messages = [{"role": "system", "content": system_prompt}] + context_messages

    collected_content: list[str] = []   # 所有已下发的文本（用于持久化）
    dispatch_calls: list[dict] = []     # 主 Agent 的所有派发记录（用于持久化）
    last_tool_messages: list[dict] = [] # 最近一次派发的结果（用于兜底回复）
    rounds = 0

    # ---- 第 3 步：主 Agent 循环（流式 + 派发） ----
    while True:
        stream_result = StreamResult()
        round_text: list[str] = []

        try:
            async for token in provider.chat_stream_with_tools(
                messages=messages,
                tools=tools,
                result=stream_result,
            ):
                if token is None:
                    # 推理阶段（reasoning_content），发心跳保活
                    yield HEARTBEAT
                else:
                    round_text.append(token)
                    collected_content.append(token)
                    yield _content_sse(token)
        except Exception as e:
            logger.error(f"LLM 流式请求失败: {type(e).__name__}: {e}")
            yield _content_sse(_friendly_error(e, provider))
            yield "data: [DONE]\n\n"
            return

        # 没有派发 → 本轮文字就是最终回复
        if not stream_result.tool_calls:
            if rounds == 0:
                logger.info(f"📝 未派发子 Agent，主 Agent 直接回复 (长度={len(''.join(round_text))})")
            break

        # ---- 有派发：记录主 Agent 的 tool_calls 消息 ----
        tool_calls = stream_result.tool_calls
        logger.info(
            f"🧭 第 {rounds + 1} 轮派发 {len(tool_calls)} 个子任务: "
            f"{[(tc.name, str(tc.arguments.get('task', ''))[:30]) for tc in tool_calls]}"
        )
        payload_calls = _tool_calls_payload(tool_calls)
        messages.append({
            "role": "assistant",
            "content": "".join(round_text),
            "tool_calls": payload_calls,
        })
        dispatch_calls.extend(payload_calls)
        rounds += 1

        # ---- 并行执行子 Agent，边执行边推送事件与心跳 ----
        yield HEARTBEAT
        queue: asyncio.Queue = asyncio.Queue()
        dispatch_task = asyncio.create_task(
            orchestrator.execute(tool_calls, provider, queue.put_nowait, sub_providers)
        )

        while True:
            if dispatch_task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=DISPATCH_HEARTBEAT_SECONDS
                )
            except asyncio.TimeoutError:
                # 子 Agent 还在思考/调工具，保持连接活跃
                yield HEARTBEAT
                continue
            yield _sse(event)

        try:
            tool_messages = await dispatch_task
        except Exception as e:
            logger.exception(f"子 Agent 执行异常: {e}")
            tool_messages = [
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"❌ 子 Agent 执行异常: {e}",
                }
                for tc in tool_calls
            ]

        messages.extend(tool_messages)
        last_tool_messages = tool_messages

        # ---- 派发轮数达到上限：强制收口，直接生成最终回复 ----
        if rounds >= MAX_DELEGATE_ROUNDS:
            logger.warning(f"⚠️ 已达最大派发轮数 {MAX_DELEGATE_ROUNDS}，强制生成最终回复")
            yield HEARTBEAT
            try:
                async for token in provider.chat_stream(messages=messages):
                    if token is None:
                        yield HEARTBEAT
                    else:
                        collected_content.append(token)
                        yield _content_sse(token)
            except Exception as e:
                logger.error(f"最终回复生成失败: {e}")
                yield _content_sse(f"\n❌ 生成回复时出错: {e}")
            break

    # ---- 第 4 步：兜底 —— 模型没说话但有子 Agent 结论 ----
    assistant_content = "".join(collected_content)
    if not assistant_content.strip() and last_tool_messages:
        fallback = "；".join(
            c for c in (_extract_conclusion(m) for m in last_tool_messages) if c
        ) or "已交给负责的助手处理完成。"
        collected_content.append(fallback)
        assistant_content = fallback
        yield _content_sse(fallback)

    # ---- 第 5 步：保存 assistant 回复到数据库 ----
    if assistant_content:
        await HistoryService.save_message(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            tool_calls=dispatch_calls or None,
        )

    # ---- 第 6 步：检查是否需要生成历史摘要 ----
    yield HEARTBEAT
    try:
        await HistoryService.check_and_generate_summary(session_id, provider)
    except Exception as e:
        logger.error(f"摘要生成失败（不影响对话）: {e}")

    # 发送结束标记
    yield "data: [DONE]\n\n"
