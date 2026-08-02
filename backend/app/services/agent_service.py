"""
HomeHamster Agent 服务层（v2 - 动态配置版）

核心改进：
- 从数据库动态加载 LLM 配置（支持多供应商）
- 从数据库动态加载 Agent 人设配置（名字、性格、系统提示词）
- 通过 llm_provider 工厂创建对应供应商实例
- 运行时可切换不同的大模型和 Agent 人格

流程：
1. 加载激活的 Agent 人设配置 → 构建系统提示词
2. 加载激活的 LLM 配置（或 Agent 配置中指定的） → 创建供应商实例
3. 第一轮：发送消息 + 工具定义给 LLM
4. 若 LLM 返回工具调用 → 执行工具 → 将结果回传
5. 第二轮：流式输出 LLM 最终回复（SSE 格式）
"""

import json
import logging
from typing import AsyncGenerator, Optional

from app.database import get_pool
from app.services import crud
from app.services.llm_provider import (
    LLMConfig,
    LLMProvider,
    create_provider,
    PROVIDER_PRESETS,
)
from app.services.tools import TOOLS_DEFINITION_OPENAI

logger = logging.getLogger(__name__)

# 默认系统提示词（当数据库中没有配置时使用）
DEFAULT_SYSTEM_PROMPT = """你是 HomeHamster（家庭仓鼠），一个智能家庭管理助手。
你可以帮助用户进行家庭账目管理、物品仓储管理，并提供资金使用和物品采购建议。
回答简洁实用，使用中文交流，涉及金额时使用人民币（¥）符号。

你可以调用以下工具：
- add_expense：添加账目记录（支出/收入）
- inventory_type：新增物品类别
- check_inventory：查询物品库存
"""

# 默认 Agent 人设
DEFAULT_AGENT = {
    "name": "HomeHamster",
    "avatar": "🐹",
    "personality": "",
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "temperature": 0.7,
}


def _build_system_prompt(agent_config: dict) -> str:
    """
    根据 Agent 人设配置构建系统提示词
    如果用户自定义了 system_prompt，直接使用；否则从 name + personality 自动生成
    """
    if agent_config.get("system_prompt"):
        return agent_config["system_prompt"]

    name = agent_config.get("name", "HomeHamster")
    personality = agent_config.get("personality", "")

    prompt = f"""你是 {name}，一个智能家庭管理助手。

你的核心能力：
1. **家庭账目管理**：记录支出和收入，帮助用户追踪家庭财务状况。
2. **物品仓储管理**：查询家庭物品库存，管理物品分类。
3. **智能建议**：基于用户的账目和库存数据，提供资金使用建议和物品采购建议。

你的性格特点：{personality or '友好、亲切，像一个精明能干的家庭管家。回答简洁实用，不啰嗦。'}

交流规则：
- 使用中文交流
- 涉及金额时使用人民币（¥）符号
- 当用户需要记账、查询库存等操作时，调用对应的工具函数
- 如果用户的请求不在你的能力范围内，礼貌地告知用户
"""
    return prompt


async def _load_agent_config() -> dict:
    """从数据库加载激活的 Agent 人设配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await crud.get_active_agent_config(conn)
        if config:
            return config
    # 回退到默认配置
    return DEFAULT_AGENT


async def _load_llm_config(agent_config: dict) -> Optional[LLMConfig]:
    """
    从数据库加载 LLM 配置
    优先使用 Agent 配置中指定的 llm_config_id，否则使用激活的 LLM 配置
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 优先使用 Agent 配置中指定的 LLM
        llm_config_id = agent_config.get("llm_config_id")
        if llm_config_id:
            config = await crud.get_llm_config(conn, llm_config_id)
            if config:
                return _dict_to_llm_config(config)

        # 回退到激活的 LLM 配置
        config = await crud.get_active_llm_config(conn)
        if config:
            return _dict_to_llm_config(config)

    return None


def _dict_to_llm_config(d: dict) -> LLMConfig:
    """将数据库字典转换为 LLMConfig 数据类"""
    return LLMConfig(
        id=d["id"],
        name=d["name"],
        provider=d["provider"],
        api_key=d.get("api_key", ""),
        base_url=d.get("base_url"),
        model_name=d["model_name"],
        embedding_model=d.get("embedding_model"),
        temperature=float(d.get("temperature", 0.7)),
        max_tokens=d.get("max_tokens", 4096),
    )


async def chat_stream(
    messages: list[dict],
    user_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Agent 对话流式处理（SSE 格式输出）

    流程：
    1. 加载 Agent 人设配置和 LLM 配置
    2. 创建对应供应商的 LLM 实例
    3. 第一轮请求（含工具定义）→ 判断是否需要工具调用
    4. 若有工具调用 → 执行 → 将结果回传
    5. 第二轮请求 → 流式输出最终回复

    Yields:
        SSE 格式字符串: data: {"content": "token"}\n\n
    """
    # ---- 第 0 步：加载配置 ----
    agent_config = await _load_agent_config()
    system_prompt = _build_system_prompt(agent_config)
    agent_temperature = float(agent_config.get("temperature", 0.7))

    llm_config = await _load_llm_config(agent_config)
    if llm_config is None:
        error_msg = (
            "⚠️ 尚未配置大模型。请在设置中添加 LLM 配置并激活。\n"
            "支持 OpenAI、Anthropic Claude、DeepSeek、智谱 GLM、本地 Ollama 等多种供应商。"
        )
        yield f"data: {json.dumps({'content': error_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 覆盖温度为 Agent 配置中的值
    llm_config.temperature = agent_temperature

    # 创建 LLM 供应商实例
    try:
        provider = create_provider(llm_config)
    except ValueError as e:
        yield f"data: {json.dumps({'content': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 构建完整消息列表（系统提示 + 对话历史）
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # ---- 第 1 步：第一轮请求（非流式，判断工具调用） ----
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

    # ---- 第 2 步：处理工具调用 ----
    if first_response.tool_calls:
        # 将 assistant 的工具调用消息加入历史
        # 注意：这里需要保持 OpenAI 格式的 tool_calls 结构，因为 Anthropic provider 会转换
        assistant_msg = {"role": "assistant"}
        if first_response.content:
            assistant_msg["content"] = first_response.content
        else:
            assistant_msg["content"] = ""
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

    # ---- 第 3 步：流式输出最终回复 ----
    try:
        async for token in provider.chat_stream(messages=full_messages):
            yield f"data: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"LLM 流式输出失败: {e}")
        yield f"data: {json.dumps({'content': f'❌ 流式输出中断: {str(e)}'}, ensure_ascii=False)}\n\n"

    # 发送结束标记
    yield "data: [DONE]\n\n"
