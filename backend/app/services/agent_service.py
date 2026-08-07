"""
HomeHamster Agent 服务层（v3.1 - 流式工具检测 + SSE 心跳保活）

核心改进（相比 v3）：
1. **流式工具检测**：第一轮直接用 stream=True + tools，文字 token 实时推给客户端，
   工具调用在流中收集。避免非流式等待导致连接超时（"client disconnected"）。
2. **SSE 心跳保活**：在工具执行、摘要生成等可能耗时的步骤前发送 SSE 注释心跳，
   防止浏览器/代理因长时间无数据而断开连接。
3. **避免重复请求**：无工具调用时第一轮流式响应即为最终回复，不再发第二轮请求。

流程：
1. 获取全局 AgentManager 实例 → 拿到缓存的 provider 和系统提示词
2. 保存用户消息到数据库
3. 从数据库加载滑动窗口内的上下文消息（含摘要）
4. 构建完整消息 [system_prompt] + [context_messages]
5. 流式请求 LLM（含工具定义）→ 文字 token 实时输出 + 工具调用在流中收集
6. 若有工具调用 → 执行 → 将结果加入上下文 → 再次流式输出最终回复
7. 若无工具调用 → 第 5 步的输出即为最终回复，无需第二轮请求
8. 保存 assistant 回复到数据库
9. 检查是否需要生成历史摘要
"""

import json
import logging
from typing import AsyncGenerator

from app.services.agent_manager import AgentManager
from app.services.history_service import HistoryService
from app.services.llm_provider import StreamResult
from app.services.tools import TOOLS_DEFINITION_OPENAI

logger = logging.getLogger(__name__)

# SSE 心跳（浏览器/代理会忽略以冒号开头的注释行，但连接保持活跃）
HEARTBEAT = ": heartbeat\n\n"


async def chat_stream(
    session_id: str,
    content: str,
    user_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Agent 对话流式处理（SSE 格式输出）

    v3.1 改进：
    - 流式工具检测：第一轮直接 stream=True + tools，避免非流式等待超时
    - SSE 心跳：在耗时步骤前发送心跳，防止连接断开
    - 无工具调用时不发第二轮请求，减少延迟

    Args:
        session_id: 对话会话 ID
        content: 用户最新消息内容
        user_id: 用户标识

    Yields:
        SSE 格式字符串: data: {"content": "token"}\\n\\n
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
        yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    system_prompt = manager.get_system_prompt()

    # ---- 第 1 步：保存用户消息到数据库 ----
    await HistoryService.save_message(
        session_id=session_id,
        role="user",
        content=content,
    )

    # ---- 第 2 步：从数据库加载上下文消息（滑动窗口 + 摘要） ----
    context_messages = await HistoryService.get_context_messages(session_id)

    # 构建完整消息列表（系统提示 + 上下文）
    full_messages = [{"role": "system", "content": system_prompt}] + context_messages

    # ---- 第 3 步：流式请求 LLM（含工具定义，文字实时输出） ----
    result = StreamResult()
    collected_content = []  # 收集完整回复用于持久化

    try:
        async for token in provider.chat_stream_with_tools(
            messages=full_messages,
            tools=TOOLS_DEFINITION_OPENAI,
            result=result,
        ):
            collected_content.append(token)
            yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"LLM 流式请求失败: {type(e).__name__}: {e}")
        error_str = str(e)
        # 智能判断错误类型，给出更有针对性的提示
        if "502" in error_str or "Bad Gateway" in error_str:
            error_msg = "❌ LLM 服务器返回 502 Bad Gateway，服务未正常运行。\n请检查 LLM 服务是否已启动并加载模型。"
        elif "Connection refused" in error_str or "ConnectError" in type(e).__name__:
            error_msg = "❌ 无法连接到 LLM 服务器。\n请检查服务是否已启动、端口是否正确。"
        elif "timeout" in error_str.lower() or "Timeout" in type(e).__name__:
            error_msg = "❌ 请求超时，LLM 服务响应时间过长。\n本地模型推理可能较慢，请稍后重试或减小 max_tokens。"
        elif "401" in error_str or "Unauthorized" in error_str or "api_key" in error_str.lower():
            error_msg = "❌ API Key 验证失败。\n请检查设置中的 API Key 是否正确。"
        elif "404" in error_str or "not found" in error_str.lower() or "model" in error_str.lower():
            error_msg = f"❌ 模型不存在或路径错误: {provider.config.model_name}\n请检查模型名称是否正确。"
        else:
            error_msg = f"❌ 模型调用失败: {error_str}\n请检查 LLM 配置（API Key、Base URL、模型名称等）。"
        yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ---- 第 4 步：若有工具调用，执行后流式输出最终回复 ----
    if result.tool_calls:
        logger.info(f"🔧 检测到 {len(result.tool_calls)} 个工具调用: {[tc.name for tc in result.tool_calls]}")
        # 构建带工具调用的 assistant 消息
        assistant_msg = {"role": "assistant"}
        assistant_msg["content"] = "".join(collected_content) or ""
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in result.tool_calls
        ]
        full_messages.append(assistant_msg)

        # 执行工具调用（发送心跳保活）
        yield HEARTBEAT
        tool_result_messages = await provider.execute_tool_calls(result.tool_calls)
        full_messages.extend(tool_result_messages)

        # 流式输出最终回复（工具执行后）
        yield HEARTBEAT
        try:
            async for token in provider.chat_stream(messages=full_messages):
                collected_content.append(token)
                yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"LLM 第二轮流式输出失败: {e}")
            yield f"data: {json.dumps({'content': f'❌ 流式输出中断: {str(e)}'}, ensure_ascii=False)}\n\n"

    # ---- 第 5 步：保存 assistant 回复到数据库 ----
    assistant_content = "".join(collected_content)

    # ---- 无工具调用时的日志 ----
    if not result.tool_calls:
        logger.info(f"📝 无工具调用，直接输出文本回复 (长度={len(assistant_content)})")

    if assistant_content:
        await HistoryService.save_message(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in result.tool_calls
            ] or None,
        )

    # ---- 第 6 步：检查是否需要生成历史摘要 ----
    yield HEARTBEAT
    try:
        await HistoryService.check_and_generate_summary(session_id, provider)
    except Exception as e:
        logger.error(f"摘要生成失败（不影响对话）: {e}")

    # 发送结束标记
    yield "data: [DONE]\n\n"
