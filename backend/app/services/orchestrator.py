"""
主 Agent 编排器（主从架构中的"主"）

职责：
1. 维护主 Agent 的系统提示词（人设 + 子 Agent 花名册 + 分派规则）
2. 提供主 Agent 可调用的委派工具定义（由子 Agent 注册表自动生成）
3. 执行委派：并行调用子 Agent，把结果聚合成 tool 消息回传主 Agent
4. 通过 on_event 回调把子 Agent 的执行状态实时推给前端

设计取舍：
- 主 Agent 不持有任何数据库工具，只能"派活"，职责单一、提示词稳定。
- 子 Agent 之间并行执行（asyncio.gather）：一次采购需要"记账 + 入库"时两条线同时跑。
- 单个子 Agent 失败不影响其他子 Agent，错误以文本形式回传，由主 Agent 组织语言告知用户。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from app.services.agents import (
    DELEGATE_TOOLS,
    list_agents,
    resolve_delegate_tool,
    roster_markdown,
)

logger = logging.getLogger(__name__)

# 事件回调：同步函数，agent_service 里会塞进 asyncio.Queue
EventSink = Callable[[dict], None]


# ============================================================
# 系统提示词
# ============================================================

MASTER_PROMPT_TEMPLATE = """你是{name}，这个家的家庭管理助手，同时也是一个「小团队的主管」。

## 你的团队（子 Agent）
你不是自己动手查库改数，而是把任务交给擅长的子 Agent 去办，再把结果汇总成一句话回复用户。

{roster}

## 工作流程
1. 先判断用户这句话属于哪一类：记账 / 库存 / 两者都有 / 闲聊咨询。
2. 需要读写数据时，调用对应的 `delegate_to_*` 工具，把任务写清楚。
3. 子 Agent 会返回「执行结论 + 执行明细」；你只转述它确认过的事实。
4. 多个子 Agent 的结果，合并成一段自然、简短的中文回复。

## 分派规则（重要）
- 一句话里有多件事，就分别派发；同一轮可以同时调用多个 `delegate_to_*` 工具，它们会并行执行。
- 「买了一箱牛奶 60 元」= 记账（支出 60 元 / 分类购物）+ 库存（牛奶 +1 箱）：
  两个子 Agent 都要派，并在任务里注明"这是同一次采购，你只负责其中一半"。
- 任务描述必须自包含：子 Agent 看不到用户原话。把金额、分类、账本、物品名、数量、单位、
  存放位置、时间范围都写进去；能从上下文推断的直接填上，不要把问题再抛回给用户。
- 纯闲聊、给建议、解释概念这类不需要真实数据的请求，直接回答，不用派发。
- 用户只说"记一下"却没说金额/物品等关键信息时，先问清楚，不要瞎填数字。
- 不确定账本名时，可以在任务里让记账专家先自己去查账本列表。

## 回复规则
- 只陈述子 Agent 确认过的结果，绝不编造金额、账目、库存数字。
- 不向用户暴露内部实现：不要提「子 Agent」「工具调用」「delegate_to_xxx」，也不要输出 JSON。
  用户问起分工时，可以说"我让负责记账 / 库存的助手去办了"。
- 子 Agent 失败时如实说明原因，并给出下一步建议（例如账本名不存在，就说明可用账本）。
- 金额用 ¥ 表示；回答简洁，能一两行说完就不要铺开。

## 你的性格
{personality}
"""

DEFAULT_PERSONALITY = "友好、亲切，像一个精明能干的家庭管家。回答简洁实用，不啰嗦。"


def build_master_system_prompt(agent_config: dict) -> str:
    """
    构建主 Agent 的系统提示词。

    - 用户在前端自定义了 system_prompt 时，把它作为「人设」部分，
      仍然拼接主从编排规则（否则主 Agent 就不知道要派活了）。
    - 否则按 name + personality 生成。
    """
    name = agent_config.get("name") or "HomeHamster"
    custom_prompt = (agent_config.get("system_prompt") or "").strip()
    personality = (agent_config.get("personality") or "").strip() or DEFAULT_PERSONALITY

    persona_block = custom_prompt or personality

    return MASTER_PROMPT_TEMPLATE.format(
        name=name,
        roster=roster_markdown(),
        personality=persona_block,
    )


# ============================================================
# 编排器
# ============================================================

class Orchestrator:
    """主 Agent 的委派执行器（无状态，可全局复用）"""

    @staticmethod
    def get_tools() -> list[dict]:
        """主 Agent 可用的工具定义（全部是委派工具）"""
        return DELEGATE_TOOLS

    @staticmethod
    def describe_agents() -> list[dict]:
        """子 Agent 元信息（供前端/接口展示）"""
        return [
            {"key": a.key, "label": a.label, "role": a.role, "tool": a.delegate_tool_name}
            for a in list_agents()
        ]

    async def execute(
        self,
        tool_calls: list,
        provider,
        on_event: Optional[EventSink] = None,
    ) -> list[dict]:
        """
        执行主 Agent 的委派调用。

        Args:
            tool_calls: 主 Agent 产生的 ToolCallResult 列表
            provider: LLM provider（子 Agent 共用同一模型配置）
            on_event: 事件回调（start / tool / done / error）

        Returns:
            tool 角色消息列表，顺序与传入的 tool_calls 一致
        """
        if not tool_calls:
            return []

        brief = [
            "{}({})".format(tc.name, str((tc.arguments or {}).get("task", ""))[:24])
            for tc in tool_calls
        ]
        logger.info(f"🧭 主 Agent 派发 {len(tool_calls)} 个子任务: {brief}")

        results = await asyncio.gather(
            *(self._run_one(tc, provider, on_event) for tc in tool_calls)
        )
        return results

    async def _run_one(
        self,
        tool_call,
        provider,
        on_event: Optional[EventSink],
    ) -> dict:
        """执行单个委派调用，返回 tool 消息"""
        agent = resolve_delegate_tool(tool_call.name)

        if agent is None:
            logger.warning(f"⚠️ 主 Agent 调用了未知工具: {tool_call.name}")
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": (
                    f"❌ 不存在名为「{tool_call.name}」的子 Agent。"
                    f"可用工具: {[t.delegate_tool_name for t in list_agents()]}"
                ),
            }

        arguments = tool_call.arguments or {}
        task = str(arguments.get("task", "")).strip()
        context = str(arguments.get("context", "") or "").strip()

        if not task:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"❌ 分派给{agent.label}的任务描述为空，请补充具体任务后重试。",
            }

        logger.info(f"➡️ 派发给 {agent.label}: {task[:80]}")
        result = await agent.run(task, provider, context=context, on_event=on_event)

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result.to_tool_message(),
        }


# 全局单例
orchestrator = Orchestrator()
