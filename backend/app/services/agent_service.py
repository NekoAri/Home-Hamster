"""
HomeHamster Agent 服务层（v3 - 全局实例 + 历史管理）

核心改进（相比 v2）：
1. **全局 Agent 单例**：通过 AgentManager 缓存 provider 和配置，不再每次请求重新加载
2. **服务端历史管理**：消息持久化到数据库，前端只需发送最新消息 + session_id
3. **滑动窗口 + 自动摘要**：长对话自动压缩上下文，避免 token 爆炸和阻塞

流程：
1. 获取全局 AgentManager 实例 → 拿到缓存的 provider 和系统提示词
2. 保存用户消息到数据库
3. 从数据库加载滑动窗口内的上下文消息（含摘要）
4. 构建完整消息 [system_prompt] + [context_messages]
5. 第一轮 LLM 请求（含工具定义）→ 判断是否需要工具调用
6. 若有工具调用 → 执行 → 将结果加入上下文
7. 第二轮流式输出最终回复（SSE）
8. 保存 assistant 回复到数据库
9. 检查是否需要生成历史摘要
"""

import json
import logging
from typing import AsyncGenerator

from app.services.agent_manager import AgentManager
from app.services.history_service import HistoryService
from app.services.tools import TOOLS_DEFINITION_OPENAI

logger = logging.getLogger(__name__)


async def chat_stream(
    session_id: str,
    content: str,
    user_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Agent 对话流式处理（SSE 格式输出）

    v3 改进：
    - 使用全局缓存的 Agent provider（无需每次请求重新加载配置）
    - 从数据库加载历史上下文（前端只需发送最新消息）
    - 自动持久化消息和管理上下文窗口

    Args:
        session_id: 对话会话 ID
        content: 用户最新消息内容
        user_id: 用户标识

    Yields:
        SSE 格式字符串: data: {"content": "token"}\n\n
    """
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

    # ---- 第 3 步：第一轮 LLM 请求（非流式，判断工具调用） ----
    try:
        first_response = await provider.chat_with_tools(
            messages=full_messages,
            tools=TOOLS_DEFINITION_OPENAI,
        )
    except Exception as e:
        logger.error(f"LLM 第一轮请求失败: {e}")
        error_msg = f"❌ 模型调用失败: {str(e)}\n请检查 LLM 配置是否正确（API Key、Base URL、模型名称等）。"
        yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ---- 第 4 步：处理工具调用 ----
    if first_response.tool_calls:
        # 构建带工具调用的 assistant 消息
        assistant_msg = {"role": "assistant"}
        assistant_msg["content"] = first_response.content or ""
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in first_response.tool_calls
        ]
        full_messages.append(assistant_msg)

        # 执行所有工具调用
        tool_result_messages = await provider.execute_tool_calls(first_response.tool_calls)
        full_messages.extend(tool_result_messages)

        # 如果第一轮已有文本内容，先输出
        if first_response.content:
            yield f"data: {json.dumps({'content': first_response.content}, ensure_ascii=False)}\n\n"

    # ---- 第 5 步：流式输出最终回复 ----
    collected_content = []  # 收集完整回复用于持久化
    try:
        async for token in provider.chat_stream(messages=full_messages):
            collected_content.append(token)
            yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"LLM 流式输出失败: {e}")
        yield f"data: {json.dumps({'content': f'❌ 流式输出中断: {str(e)}'}, ensure_ascii=False)}\n\n"

    # ---- 第 6 步：保存 assistant 回复到数据库 ----
    assistant_content = "".join(collected_content)
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
                for tc in (first_response.tool_calls if first_response.tool_calls else [])
            ] or None,
        )

    # ---- 第 7 步：检查是否需要生成历史摘要（异步，不阻塞响应） ----
    try:
        await HistoryService.check_and_generate_summary(session_id, provider)
    except Exception as e:
        logger.error(f"摘要生成失败（不影响对话）: {e}")

    # 发送结束标记
    yield "data: [DONE]\n\n"
