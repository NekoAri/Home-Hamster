"""
子 Agent 运行框架（主从架构中的"从"）

设计要点：
1. **职责边界**：每个子 Agent 只拿到自己领域内的工具定义与函数映射，
   从机制上防止跨域操作（例如库存 Agent 无法记账）。
2. **独立 Agent Loop**：子 Agent 自己完成"思考 → 调工具 → 看结果 → 再思考"，
   全程不走用户连接、不流式输出，只把最终结论回传给主 Agent。
3. **状态事件**：执行过程中通过 on_event 回调向主 Agent/前端汇报
   start / tool / done / error 四类事件，方便展示执行轨迹。
4. **失败不抛出**：任何异常都收敛为 AgentRunResult(success=False)，
   由主 Agent 决定如何向用户解释，避免一个子任务失败拖垮整轮对话。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# 事件回调：同步函数，内部通常塞进 asyncio.Queue
EventSink = Callable[[dict], None]

# 单次工具结果回传给主 Agent 时的最大长度，避免撑爆主 Agent 上下文
MAX_TOOL_RESULT_CHARS = 800


def _brief_args(arguments: dict, limit: int = 2) -> str:
    """把工具参数压缩成一行摘要，用于前端展示"""
    if not arguments:
        return ""
    parts = []
    for key, value in list(arguments.items())[:limit]:
        text = str(value)
        if len(text) > 24:
            text = text[:24] + "…"
        parts.append(f"{key}={text}")
    return ", ".join(parts)


@dataclass
class AgentStep:
    """子 Agent 的一次工具调用记录"""

    tool: str
    arguments: dict
    result: str

    def to_line(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in self.arguments.items())
        res = self.result.strip()
        if len(res) > MAX_TOOL_RESULT_CHARS:
            res = res[:MAX_TOOL_RESULT_CHARS] + " …(已截断)"
        return f"- {self.tool}({args}) → {res}"


@dataclass
class AgentRunResult:
    """子 Agent 一次任务执行的完整结果"""

    agent: str
    label: str
    task: str
    success: bool
    content: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    rounds: int = 0
    elapsed: float = 0.0
    error: Optional[str] = None

    def summary_text(self) -> str:
        """暴露给前端的一句话摘要"""
        if not self.success:
            return self.error or "执行失败"
        text = self.content.strip().replace("\n", " ")
        return text[:60] + ("…" if len(text) > 60 else "")

    def to_tool_message(self) -> str:
        """
        转换成交给主 Agent 的 tool 消息内容。
        结构化、信息完整，但控制长度，避免占用过多上下文。
        """
        status = "成功" if self.success else "失败"
        header = (
            f"[{self.label} | {status} | {self.rounds} 轮 | {self.elapsed:.1f}s]\n"
            f"任务: {self.task}"
        )
        if self.steps:
            detail = "\n执行明细:\n" + "\n".join(s.to_line() for s in self.steps)
        else:
            detail = "\n执行明细: 未调用工具"
        body = f"\n返回结论:\n{self.content.strip() or '(空)'}"
        return header + body + detail

    def to_event_payload(self) -> dict:
        """转换成前端可用的精简结构"""
        return {
            "agent": self.agent,
            "label": self.label,
            "task": self.task,
            "success": self.success,
            "summary": self.summary_text(),
            "rounds": self.rounds,
            "elapsed": round(self.elapsed, 2),
            "tools": [s.tool for s in self.steps],
        }


class SubAgent:
    """
    子 Agent 基类。

    子类只需提供角色信息与工具集，执行逻辑统一在这里实现。
    """

    #: 唯一标识，如 "bookkeeping"
    key: str = ""
    #: 展示名，如 "📒 记账专家"
    label: str = ""
    #: 一句话职责，用于主 Agent 的提示词与工具描述
    role: str = ""
    #: 主 Agent 调用的工具名前缀，完整名为 f"delegate_to_{key}"
    #: 工具集（OpenAI 格式）
    tools: list[dict] = []
    #: 工具名 → 函数
    functions: dict[str, Callable] = {}
    #: 最多思考/调用轮数
    max_rounds: int = 4
    #: 单次任务整体超时（秒），防止本地模型卡死
    timeout: float = 180.0
    #: 是否允许主 Agent 传入会话上下文
    accept_context: bool = True

    # ------------------------------------------------------------
    # 提示词（子类实现）
    # ------------------------------------------------------------

    def build_system_prompt(self) -> str:
        """构建子 Agent 的系统提示词（子类必须实现）"""
        raise NotImplementedError

    # ------------------------------------------------------------
    # 主 Agent 看到的工具定义
    # ------------------------------------------------------------

    @property
    def delegate_tool_name(self) -> str:
        """主 Agent 用来分派任务的工具名"""
        return f"delegate_to_{self.key}"

    def build_delegate_tool(self) -> dict:
        """生成主 Agent 侧的委派工具定义"""
        properties: dict[str, Any] = {
            "task": {
                "type": "string",
                "description": (
                    f"交给{self.label}执行的完整任务描述。要写清具体要素"
                    "（金额/分类/账本/物品/数量/单位/位置/时间范围等），"
                    "子 Agent 看不到用户原话，只看你写的这段任务。"
                ),
            }
        }
        if self.accept_context:
            properties["context"] = {
                "type": "string",
                "description": "必要的背景信息（如'这是同一次采购的一半，请只负责记账'），可为空。",
            }
        return {
            "type": "function",
            "function": {
                "name": self.delegate_tool_name,
                "description": f"把任务分派给{self.label}。职责范围：{self.role}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": ["task"],
                },
            },
        }

    # ------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------

    async def run(
        self,
        task: str,
        provider,
        context: str = "",
        on_event: Optional[EventSink] = None,
    ) -> AgentRunResult:
        """
        执行一次任务。

        Args:
            task: 主 Agent 写的任务描述
            provider: LLM provider（与主 Agent 共用）
            context: 上下文补充
            on_event: 事件回调（start/tool/done/error）

        Returns:
            AgentRunResult，永不抛异常
        """
        started = time.monotonic()
        result = AgentRunResult(
            agent=self.key,
            label=self.label,
            task=task,
            success=False,
        )

        self._emit(on_event, "start", task=task)

        messages = [
            {"role": "system", "content": self.build_system_prompt()},
            {"role": "user", "content": self._build_user_prompt(task, context)},
        ]

        try:
            content = await asyncio.wait_for(
                self._loop(messages, result, on_event, provider),
                timeout=self.timeout,
            )
            result.content = content or ""
            # 有内容即视为成功；即使工具报错，子 Agent 也会说明情况
            result.success = bool(result.content.strip())
            if not result.success:
                result.error = "子 Agent 未返回任何结论"
        except asyncio.TimeoutError:
            result.success = False
            result.error = f"执行超时（>{self.timeout:.0f}s）"
            logger.error(f"⏱️ {self.label} 执行超时 task={task!r}")
        except Exception as e:  # noqa: BLE001 - 子 Agent 失败不应中断主流程
            result.success = False
            result.error = f"{type(e).__name__}: {e}"
            logger.exception(f"❌ {self.label} 执行失败: {e}")

        result.elapsed = time.monotonic() - started
        self._emit(
            on_event,
            "done" if result.success else "error",
            **result.to_event_payload(),
        )
        logger.info(
            f"🤖 {self.label} 完成 | success={result.success} "
            f"rounds={result.rounds} steps={len(result.steps)} {result.elapsed:.1f}s"
        )
        return result

    async def _loop(
        self,
        messages: list[dict],
        result: AgentRunResult,
        on_event: Optional[EventSink],
        provider,
    ) -> str:
        """子 Agent 的 ReAct 循环：LLM → 工具 → 再 LLM"""
        for round_no in range(1, self.max_rounds + 1):
            result.rounds = round_no
            response = await _provider_chat(provider, messages, self.tools)

            if not response.tool_calls:
                return response.content or ""

            # 记录 assistant 的工具调用消息
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _json_dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            })

            # 逐个执行工具
            for tc in response.tool_calls:
                tool_result = await self._call_tool(tc)
                result.steps.append(
                    AgentStep(tool=tc.name, arguments=tc.arguments, result=tool_result)
                )
                self._emit(
                    on_event,
                    "tool",
                    tool=tc.name,
                    detail=_brief_args(tc.arguments),
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        # 轮数用尽：让模型基于已有工具结果直接给结论（不再允许调工具）
        logger.warning(f"⚠️ {self.label} 达到最大轮数 {self.max_rounds}，强制收敛结论")
        messages.append({
            "role": "user",
            "content": "请基于以上已获得的信息直接给出最终结论，不要再调用工具。",
        })
        response = await _provider_chat(provider, messages, [])
        return response.content or ""

    async def _call_tool(self, tool_call) -> str:
        """执行单个工具调用（限定在子 Agent 自己的工具集内）"""
        func = self.functions.get(tool_call.name)
        if func is None:
            return f"❌ 未知工具: {tool_call.name}"
        try:
            return await func(**tool_call.arguments)
        except TypeError as e:
            logger.error(f"工具 {tool_call.name} 参数错误: {e}")
            return f"❌ 参数错误: {e}"
        except Exception as e:  # noqa: BLE001
            logger.exception(f"工具 {tool_call.name} 执行失败: {e}")
            return f"❌ 工具执行出错: {e}"

    # ------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------

    def _build_user_prompt(self, task: str, context: str) -> str:
        today = datetime.now()
        lines = [
            f"今天是 {today.strftime('%Y-%m-%d')}（{_weekday_cn(today)}）。",
            "",
            "【主 Agent 给你的任务】",
            task.strip(),
        ]
        if context:
            lines += ["", "【补充背景】", context.strip()]
        lines += [
            "",
            "请在你的职责范围内完成任务：需要数据就调用工具，不要凭空编造；"
            "完成后用简短的中文汇报结果（做了什么、关键数字、异常点）。",
        ]
        return "\n".join(lines)

    def _emit(self, on_event: Optional[EventSink], event: str, **kwargs) -> None:
        """
        向主流程汇报执行状态。

        事件结构（前端直接消费）：
            {"type": "agent_event", "event": "start|tool|done|error",
             "agent": "bookkeeping", "label": "📒 记账专家", ...}
        """
        if on_event is None:
            return
        try:
            on_event({
                "type": "agent_event",
                "event": event,
                "agent": self.key,
                "label": self.label,
                **kwargs,
            })
        except Exception:  # noqa: BLE001 - 事件回调失败不影响执行
            logger.debug("事件回调失败", exc_info=True)


# ----------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------

def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def _weekday_cn(dt: datetime) -> str:
    return "周" + "一二三四五六日"[dt.weekday()]


async def _provider_chat(provider, messages: list[dict], tools: list[dict]):
    """
    统一的 provider 调用入口。

    tools 为空时走 chat_stream 拼装（部分供应商不接受空 tools），
    否则走 chat_with_tools。
    """
    if tools:
        return await provider.chat_with_tools(messages, tools)

    # 无工具：用流式接口收集完整文本，兼容所有供应商
    chunks: list[str] = []
    async for token in provider.chat_stream(messages):
        if token:
            chunks.append(token)

    class _Resp:
        tool_calls: list = []
        content = "".join(chunks)

    return _Resp()
