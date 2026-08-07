"""
HomeHamster 多供应商 LLM 调用适配层

设计目标：
- 统一抽象不同大模型供应商的 API 差异（OpenAI / Anthropic / Ollama / DeepSeek 等）
- 统一 Function Calling 工具格式转换
- 统一流式输出接口
- 通过数据库配置动态选择供应商，运行时切换

支持的供应商：
  - openai:    OpenAI 官方 API（gpt-4o, gpt-4o-mini 等）
  - anthropic: Anthropic Claude API（claude-3-5-sonnet 等）
  - ollama:    本地 Ollama（qwen2, llama3 等，OpenAI 兼容接口）
  - deepseek:  DeepSeek API（deepseek-chat 等，OpenAI 兼容接口）
  - zhipu:     智谱 GLM API（glm-4 等，OpenAI 兼容接口）
  - azure:     Azure OpenAI
  - custom:    自定义 OpenAI 兼容接口

架构：
  LLMProvider (抽象基类)
    ├── OpenAICompatibleProvider  — 覆盖 openai/ollama/deepseek/zhipu/azure/custom
    └── AnthropicProvider         — 覆盖 anthropic
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from app.services.tools import TOOLS_DEFINITION_OPENAI, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class LLMConfig:
    """LLM 配置数据（从数据库加载）"""
    id: int
    name: str
    provider: str          # openai / anthropic / ollama / deepseek / zhipu / azure / custom
    api_key: str
    base_url: Optional[str]
    model_name: str
    embedding_model: Optional[str]
    temperature: float
    max_tokens: int


@dataclass
class ToolCallResult:
    """工具调用结果"""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM 第一轮响应（非流式）"""
    content: Optional[str] = None             # 文本内容
    tool_calls: list[ToolCallResult] = field(default_factory=list)  # 工具调用列表


@dataclass
class StreamResult:
    """流式响应结果持有者（用于在流式输出中收集工具调用）"""
    tool_calls: list[ToolCallResult] = field(default_factory=list)


# ============================================================
# 抽象基类
# ============================================================

class LLMProvider(ABC):
    """LLM 供应商抽象基类，定义统一接口"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """
        发送对话请求（含工具定义），获取第一轮响应
        返回文本内容或工具调用
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        发送对话请求（流式输出），逐 token 返回文本
        不携带工具定义，用于工具执行后的最终回复
        """
        ...

    async def chat_stream_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        result: "StreamResult",
    ) -> AsyncGenerator[str, None]:
        """
        流式输出 + 工具调用检测（一体化）

        文本 token 通过 yield 实时返回，工具调用存入 result.tool_calls。
        默认实现：非流式调用后一次性返回（子类可覆写为真正的流式）。
        """
        response = await self.chat_with_tools(messages, tools)
        result.tool_calls = response.tool_calls
        if response.content:
            yield response.content

    async def execute_tool_calls(self, tool_calls: list[ToolCallResult]) -> list[dict]:
        """
        执行工具调用，返回 tool 角色消息列表
        通用逻辑，各供应商共用
        """
        results = []
        for tc in tool_calls:
            logger.info(f"🔧 工具调用: {tc.name}({tc.arguments})")
            if tc.name in TOOL_FUNCTIONS:
                try:
                    result = await TOOL_FUNCTIONS[tc.name](**tc.arguments)
                except Exception as e:
                    result = f"❌ 工具执行出错: {str(e)}"
                    logger.error(f"工具 {tc.name} 执行失败: {e}")
            else:
                result = f"❌ 未知工具: {tc.name}"
            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        return results


# ============================================================
# OpenAI 兼容供应商（覆盖 openai / ollama / deepseek / zhipu / azure / custom）
# ============================================================

class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI 兼容接口供应商
    适用于所有支持 OpenAI API 格式的服务
    """

    # 各供应商默认 base_url（当数据库中 base_url 为空时使用）
    DEFAULT_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "ollama": "http://localhost:11434/v1",
        "azure": "",  # Azure 需用户填写
        "custom": "",  # 自定义需用户填写
    }

    def _get_client(self):
        """创建 OpenAI Async 客户端"""
        from openai import AsyncOpenAI
        base_url = self.config.base_url or self.DEFAULT_BASE_URLS.get(
            self.config.provider, ""
        )
        # 本地模型（Ollama/自定义局域网）推理较慢，设较长超时
        is_local = self.config.provider in ("ollama", "custom") or (
            base_url and ("localhost" in base_url or "192.168." in base_url or "127.0.0.1" in base_url)
        )
        return AsyncOpenAI(
            api_key=self.config.api_key or "dummy",  # Ollama 等本地模型无需 key
            base_url=base_url if base_url else None,
            timeout=300.0 if is_local else 60.0,  # 本地5分钟，云服务1分钟
            max_retries=1,  # 减少重试，避免本地服务异常时长时间卡住
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """使用 OpenAI 接口发送带工具的对话请求"""
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        choice = response.choices[0]
        message = choice.message

        # 解析工具调用
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCallResult(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
        )

    async def chat_stream(
        self,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """使用 OpenAI 接口流式输出"""
        client = self._get_client()
        stream = await client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            stream=True,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    async def chat_stream_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        result: "StreamResult",
    ) -> AsyncGenerator[str, None]:
        """
        流式输出 + 工具调用检测（一体化）

        使用 OpenAI stream=True + tools 参数，文字 token 实时 yield，
        工具调用 delta 在流中收集，流结束后存入 result.tool_calls。
        避免非流式第一轮请求导致连接超时。

        回退机制：如果流式响应既没有文本内容也没有工具调用，
        可能是模型/服务器不支持流式工具调用，自动回退到非流式请求。
        """
        client = self._get_client()
        stream = await client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=True,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # 工具调用 delta 累积器: index -> {id, name, arguments}
        tool_acc: dict[int, dict] = {}
        has_content = False

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 流式输出文本
            if delta.content:
                has_content = True
                yield delta.content

            # 收集工具调用 delta
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_acc:
                        tool_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_acc[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_acc[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_acc[idx]["arguments"] += tc.function.arguments

        # 流结束后，构建完整的工具调用列表
        for idx in sorted(tool_acc.keys()):
            tc = tool_acc[idx]
            if tc["id"] and tc["name"]:
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    logger.warning(f"工具调用参数 JSON 解析失败: {tc['arguments']}")
                    args = {}
                result.tool_calls.append(ToolCallResult(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=args,
                ))
                logger.info(f"🔧 流式检测到工具调用: {tc['name']}({args})")

        # 回退：流式响应既无文本也无工具调用 → 尝试非流式
        if not has_content and not result.tool_calls:
            logger.warning("⚠️ 流式响应无内容无工具调用，回退到非流式请求...")
            try:
                response = await client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                msg = response.choices[0].message
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        result.tool_calls.append(ToolCallResult(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=args,
                        ))
                        logger.info(f"🔧 非流式检测到工具调用: {tc.function.name}({args})")
                if msg.content:
                    yield msg.content
            except Exception as e:
                logger.error(f"非流式回退请求失败: {e}")
                raise


# ============================================================
# Anthropic Claude 供应商
# ============================================================

class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude 供应商
    Claude 的 API 格式与 OpenAI 不同，需要单独适配
    """

    # Claude 模型的工具调用格式与 OpenAI 不同，需要转换
    def _get_client(self):
        """创建 Anthropic Async 客户端"""
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=self.config.api_key)

    def _convert_tools_to_anthropic(self, tools: list[dict]) -> list[dict]:
        """
        将 OpenAI 格式的工具定义转换为 Anthropic 格式
        OpenAI:  {type: "function", function: {name, description, parameters}}
        Anthropic: {name, description, input_schema}
        """
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"],
            })
        return anthropic_tools

    def _convert_messages_to_anthropic(
        self, messages: list[dict]
    ) -> tuple[str, list[dict]]:
        """
        将 OpenAI 格式的消息转换为 Anthropic 格式
        Anthropic 要求 system 消息单独传递，其余消息中的 tool 结果需要特殊处理
        返回: (system_prompt, messages)
        """
        system_prompt = ""
        converted = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "assistant" and "tool_calls" in msg:
                # 包含工具调用的 assistant 消息需要转换为 Anthropic 格式
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                converted.append({"role": "assistant", "content": content_blocks})
            elif msg["role"] == "tool":
                # 工具结果需要包裹在 tool_result 块中
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg["content"],
                    }],
                })
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})

        return system_prompt, converted

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """使用 Anthropic 接口发送带工具的对话请求"""
        client = self._get_client()
        system_prompt, converted_messages = self._convert_messages_to_anthropic(messages)
        anthropic_tools = self._convert_tools_to_anthropic(tools)

        response = await client.messages.create(
            model=self.config.model_name,
            system=system_prompt,
            messages=converted_messages,
            tools=anthropic_tools,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        # 解析 Anthropic 响应
        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCallResult(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return LLMResponse(content=content, tool_calls=tool_calls)

    async def chat_stream(
        self,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """使用 Anthropic 接口流式输出"""
        client = self._get_client()
        system_prompt, converted_messages = self._convert_messages_to_anthropic(messages)

        async with client.messages.stream(
            model=self.config.model_name,
            system=system_prompt,
            messages=converted_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text


# ============================================================
# 供应商工厂
# ============================================================

# 供应商类型到实现类的映射
PROVIDER_CLASSES = {
    "openai": OpenAICompatibleProvider,
    "ollama": OpenAICompatibleProvider,
    "deepseek": OpenAICompatibleProvider,
    "zhipu": OpenAICompatibleProvider,
    "azure": OpenAICompatibleProvider,
    "custom": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
}

# 供应商展示信息（供前端下拉选择使用）
PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "needs_api_key": True,
        "description": "OpenAI 官方 API，支持 GPT-4o、GPT-4o-mini 等模型",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "default_base_url": "",
        "default_model": "claude-3-5-sonnet-20241022",
        "needs_api_key": True,
        "description": "Anthropic Claude，擅长长文本分析和推理",
    },
    "deepseek": {
        "label": "DeepSeek",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "needs_api_key": True,
        "description": "DeepSeek 深度求索，性价比高",
    },
    "zhipu": {
        "label": "智谱 GLM",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4",
        "needs_api_key": True,
        "description": "智谱 AI GLM 系列模型",
    },
    "ollama": {
        "label": "Ollama (本地)",
        "default_base_url": "http://localhost:11434/v1",
        "default_model": "qwen2:7b",
        "needs_api_key": False,
        "description": "本地 Ollama 部署，数据不出本地，支持 Qwen/Llama3 等",
    },
    "custom": {
        "label": "自定义 (OpenAI 兼容)",
        "default_base_url": "",
        "default_model": "",
        "needs_api_key": True,
        "description": "任何兼容 OpenAI API 格式的服务",
    },
}


def create_provider(config: LLMConfig) -> LLMProvider:
    """
    工厂方法：根据配置创建对应的 LLM 供应商实例

    Args:
        config: 从数据库加载的 LLM 配置

    Returns:
        LLMProvider 实例

    Raises:
        ValueError: 不支持的供应商类型
    """
    provider_class = PROVIDER_CLASSES.get(config.provider)
    if provider_class is None:
        raise ValueError(
            f"不支持的供应商类型: {config.provider}。"
            f"支持的类型: {list(PROVIDER_CLASSES.keys())}"
        )
    return provider_class(config)
