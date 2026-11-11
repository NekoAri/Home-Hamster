"""
子 Agent 注册表

新增子 Agent 只需：
1. 在 agents/ 下新建一个 SubAgent 子类（定义 key / label / role / tools / 提示词）
2. 把类加入下面的 SUB_AGENT_CLASSES

主 Agent 的委派工具、系统提示词中的花名册、前端展示文案都会自动同步。
"""

from app.services.agents.base import SubAgent
from app.services.agents.bookkeeping import BookkeepingAgent
from app.services.agents.inventory import InventoryAgent

# 注册顺序即展示顺序
SUB_AGENT_CLASSES: tuple[type[SubAgent], ...] = (
    BookkeepingAgent,
    InventoryAgent,
)

# key -> 单例实例
SUB_AGENTS: dict[str, SubAgent] = {cls.key: cls() for cls in SUB_AGENT_CLASSES}

# 主 Agent 工具名 -> 子 Agent
DELEGATE_TOOL_MAP: dict[str, SubAgent] = {
    agent.delegate_tool_name: agent for agent in SUB_AGENTS.values()
}

# 主 Agent 可用的委派工具定义（OpenAI 格式）
DELEGATE_TOOLS: list[dict] = [agent.build_delegate_tool() for agent in SUB_AGENTS.values()]


def get_agent(key: str) -> SubAgent | None:
    """按 key 获取子 Agent"""
    return SUB_AGENTS.get(key)


def list_agents() -> list[SubAgent]:
    """按注册顺序返回所有子 Agent"""
    return list(SUB_AGENTS.values())


def resolve_delegate_tool(tool_name: str) -> SubAgent | None:
    """把主 Agent 的工具名解析为子 Agent"""
    return DELEGATE_TOOL_MAP.get(tool_name)


def roster_markdown() -> str:
    """生成给主 Agent 看的子 Agent 花名册（Markdown 表格）"""
    lines = ["| 子 Agent | 工具名 | 职责 |", "| --- | --- | --- |"]
    for agent in SUB_AGENTS.values():
        lines.append(f"| {agent.label} | `{agent.delegate_tool_name}` | {agent.role} |")
    return "\n".join(lines)
