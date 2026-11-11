"""
HomeHamster 子 Agent 包（主从架构中的"从"）

对外主要入口：
- SUB_AGENTS / list_agents()      子 Agent 注册表
- DELEGATE_TOOLS                  主 Agent 可用的委派工具定义
- resolve_delegate_tool(name)     工具名 -> 子 Agent
- roster_markdown()               提示词里的花名册
"""

from app.services.agents.base import AgentRunResult, AgentStep, SubAgent
from app.services.agents.registry import (
    DELEGATE_TOOLS,
    SUB_AGENTS,
    get_agent,
    list_agents,
    resolve_delegate_tool,
    roster_markdown,
)

__all__ = [
    "AgentRunResult",
    "AgentStep",
    "SubAgent",
    "DELEGATE_TOOLS",
    "SUB_AGENTS",
    "get_agent",
    "list_agents",
    "resolve_delegate_tool",
    "roster_markdown",
]
