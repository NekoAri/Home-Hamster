"""
主从 Agent 架构的最小验证（不依赖数据库、不依赖真实 LLM）

运行方式：
    cd backend && python tests/test_master_slave.py

覆盖：
1. 子 Agent 的 ReAct 循环（工具调用 → 再思考 → 结论）
2. 事件流（start / tool / done）结构与字段
3. 主 Agent 并行派发多个子 Agent
4. 未知工具、空任务的容错
5. 主 Agent 系统提示词包含子 Agent 花名册
6. 子 Agent 工具作用域隔离（记账 Agent 拿不到库存工具）
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.orchestrator as orch_module  # noqa: E402
from app.services.agents.base import AgentRunResult, SubAgent  # noqa: E402
from app.services.agents.bookkeeping import BookkeepingAgent  # noqa: E402
from app.services.agents.inventory import InventoryAgent  # noqa: E402
from app.services.llm_provider import LLMResponse, ToolCallResult  # noqa: E402
from app.services.orchestrator import Orchestrator, build_master_system_prompt  # noqa: E402


# ============================================================
# 测试替身
# ============================================================

class FakeProvider:
    """按脚本返回预设响应，记录收到的消息与工具定义"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.seen: list[tuple[list, list]] = []

    async def chat_with_tools(self, messages, tools):
        self.seen.append((messages, tools))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def chat_stream(self, messages):
        self.seen.append((messages, []))
        for chunk in ("兜底", "回复"):
            yield chunk


class EchoAgent(SubAgent):
    """测试用子 Agent：只暴露一个 ping 工具"""

    key = "echo"
    label = "🔁 回显专家"
    role = "测试用回显"
    tools = [{
        "type": "function",
        "function": {
            "name": "ping",
            "description": "ping",
            "parameters": {"type": "object", "properties": {}},
        },
    }]
    functions: dict = {}
    max_rounds = 2

    def build_system_prompt(self) -> str:
        return "你是回显专家，只负责回显。"


class FakeDelegate:
    """主 Agent 侧的假子 Agent，用于测试并行派发"""

    def __init__(self, key: str, label: str, delay: float = 0.0):
        self.key = key
        self.label = label
        self.delay = delay
        self.delegate_tool_name = f"delegate_to_{key}"
        self.tasks: list[str] = []
        self.providers: list = []

    async def run(self, task, provider, context="", on_event=None):
        self.tasks.append(task)
        self.providers.append(provider)
        if on_event:
            on_event({
                "type": "agent_event", "event": "start",
                "agent": self.key, "label": self.label, "task": task,
            })
        await asyncio.sleep(self.delay)
        if on_event:
            on_event({
                "type": "agent_event", "event": "done",
                "agent": self.key, "label": self.label, "success": True,
            })
        return AgentRunResult(
            agent=self.key,
            label=self.label,
            task=task,
            success=True,
            content=f"{self.label} 已完成：{task}",
            rounds=1,
            elapsed=self.delay,
        )


# ============================================================
# 用例
# ============================================================

async def test_subagent_loop() -> None:
    """子 Agent 应先调工具、再基于工具结果给出结论"""
    agent = EchoAgent()
    received: list[dict] = []

    async def ping(**kwargs):
        received.append(kwargs)
        return "pong"

    agent.functions = {"ping": ping}
    provider = FakeProvider([
        LLMResponse(content="", tool_calls=[
            ToolCallResult(id="call_1", name="ping", arguments={"x": 1})
        ]),
        LLMResponse(content="已回显完成", tool_calls=[]),
    ])
    events: list[dict] = []

    result = await agent.run("测试任务", provider, on_event=events.append)

    assert result.success, result.error
    assert result.content == "已回显完成"
    assert result.rounds == 2
    assert received == [{"x": 1}], received
    assert result.steps[0].tool == "ping"
    assert [e["event"] for e in events] == ["start", "tool", "done"], events
    assert all(e["agent"] == "echo" and e["label"] == agent.label for e in events)
    print("✅ 1. 子 Agent ReAct 循环 + 事件流正常")


async def test_subagent_unknown_tool() -> None:
    """子 Agent 调用不存在的工具时应回传错误而不是崩溃"""
    agent = EchoAgent()
    agent.functions = {}
    provider = FakeProvider([
        LLMResponse(content="", tool_calls=[
            ToolCallResult(id="call_404", name="not_exist", arguments={})
        ]),
        LLMResponse(content="工具不存在，无法完成", tool_calls=[]),
    ])

    result = await agent.run("非法工具测试", provider)

    assert result.success
    assert "未知工具" in result.steps[0].result
    assert "工具不存在" in result.content
    print("✅ 2. 未知工具容错正常")


async def test_subagent_provider_error() -> None:
    """LLM 报错时应收敛为失败结果，不向上抛异常"""
    agent = EchoAgent()
    agent.functions = {}
    provider = FakeProvider([RuntimeError("boom")])

    result = await agent.run("异常测试", provider)

    assert not result.success
    assert "boom" in (result.error or "")
    print("✅ 3. 子 Agent 异常收敛正常")


async def test_orchestrator_parallel() -> None:
    """一次派发多个子 Agent 时应并行执行，且结果按调用顺序回传"""
    bookkeeping = FakeDelegate("bookkeeping", "📒 记账专家", delay=0.3)
    inventory = FakeDelegate("inventory", "📦 库存专家", delay=0.3)
    table = {a.delegate_tool_name: a for a in (bookkeeping, inventory)}

    original = orch_module.resolve_delegate_tool
    orch_module.resolve_delegate_tool = lambda name: table.get(name)  # type: ignore[assignment]
    try:
        tool_calls = [
            ToolCallResult(id="c1", name="delegate_to_bookkeeping",
                           arguments={"task": "记录支出 60 元，分类购物"}),
            ToolCallResult(id="c2", name="delegate_to_inventory",
                           arguments={"task": "牛奶入库 1 箱，位置冰箱"}),
        ]
        events: list[dict] = []
        started = asyncio.get_event_loop().time()
        messages = await Orchestrator().execute(tool_calls, provider=None, on_event=events.append)
        elapsed = asyncio.get_event_loop().time() - started
    finally:
        orch_module.resolve_delegate_tool = original  # type: ignore[assignment]

    assert len(messages) == 2
    assert messages[0]["tool_call_id"] == "c1"
    assert "记账专家" in messages[0]["content"]
    assert "牛奶入库" in messages[1]["content"]
    # 两个 0.3s 的任务并行执行，总耗时明显小于串行的 0.6s
    assert elapsed < 0.55, f"未并行执行，耗时 {elapsed:.2f}s"
    assert [e["event"] for e in events] == ["start", "start", "done", "done"]
    print(f"✅ 4. 并行派发正常（总耗时 {elapsed:.2f}s < 0.6s）")


async def test_orchestrator_unknown_tool_and_empty_task() -> None:
    """未知工具 / 空任务应返回可读错误，不抛异常"""
    original = orch_module.resolve_delegate_tool
    orch_module.resolve_delegate_tool = lambda name: None  # type: ignore[assignment]
    try:
        messages = await Orchestrator().execute(
            [ToolCallResult(id="x", name="delegate_to_nobody", arguments={"task": "hi"})],
            provider=None,
        )
    finally:
        orch_module.resolve_delegate_tool = original  # type: ignore[assignment]

    assert "不存在名为" in messages[0]["content"]

    agent = FakeDelegate("bookkeeping", "📒 记账专家")
    orch_module.resolve_delegate_tool = lambda name: agent if name == agent.delegate_tool_name else None  # type: ignore[assignment]
    try:
        messages = await Orchestrator().execute(
            [ToolCallResult(id="y", name="delegate_to_bookkeeping", arguments={"task": "  "})],
            provider=None,
        )
    finally:
        orch_module.resolve_delegate_tool = original  # type: ignore[assignment]

    assert "任务描述为空" in messages[0]["content"]
    print("✅ 5. 未知工具 / 空任务容错正常")


async def test_chat_stream_end_to_end() -> None:
    """
    端到端跑一遍 chat_stream：
    主 Agent 派发 → 子 Agent 事件下发 → 最终回复流式输出 → 落库
    （DB 与 LLM 全部用测试替身，验证编排逻辑与 SSE 帧格式）
    """
    import app.services.agent_service as agent_service
    from app.services.llm_provider import ToolCallResult

    dispatch_calls = [ToolCallResult(
        id="call_1",
        name="delegate_to_bookkeeping",
        arguments={"task": "记录支出 25 元，分类餐饮"},
    )]

    class FakeStreamProvider:
        """第一轮流式吐出"我让记账助手去办"，并声明一次派发；第二轮吐最终回复"""

        def __init__(self):
            self.rounds = [
                (["好的", "，", "这就去记。"], dispatch_calls),
                (["已", "记好", "啦"], []),
            ]

        async def chat_stream_with_tools(self, messages, tools, result):
            tokens, tool_calls = self.rounds.pop(0)
            for token in tokens:
                yield token
            result.tool_calls = list(tool_calls)

        async def chat_stream(self, messages):
            for token in ("已", "记好", "啦"):
                yield token

    class FakeManager:
        async def get_provider(self):
            return FakeStreamProvider()

        def get_system_prompt(self):
            return "你是主 Agent"

        def get_sub_providers(self):
            return {}  # 测试环境无独立模型绑定，全部回退主模型

    saved: list[dict] = []

    async def fake_save_message(session_id, role, content, tool_calls=None):
        saved.append({"role": role, "content": content, "tool_calls": tool_calls})

    async def fake_get_context(session_id):
        return []

    async def noop_summary(session_id, provider):
        return None

    async def fake_execute(tool_calls, provider, on_event=None, sub_providers=None):
        if on_event:
            on_event({"type": "agent_event", "event": "start",
                      "agent": "bookkeeping", "label": "📒 记账专家",
                      "task": "记录支出 25 元"})
            await asyncio.sleep(0)
            on_event({"type": "agent_event", "event": "done",
                      "agent": "bookkeeping", "label": "📒 记账专家", "success": True,
                      "summary": "已记账 ¥25", "tools": ["add_expense"], "elapsed": 0.1})
        return [{
            "role": "tool",
            "tool_call_id": tc.id,
            "content": (
                "[📒 记账专家 | 成功 | 1 轮 | 0.1s]\n"
                f"任务: {tc.arguments['task']}\n"
                "返回结论:\n已记账 ¥25，分类餐饮\n"
                "执行明细:\n- add_expense(amount=25) → ✅"
            ),
        } for tc in tool_calls]

    # ---- 打桩 ----
    originals = {
        "get_instance": agent_service.AgentManager.get_instance,
        "save_message": agent_service.HistoryService.save_message,
        "get_context": agent_service.HistoryService.get_context_messages,
        "summary": agent_service.HistoryService.check_and_generate_summary,
        "execute": agent_service.orchestrator.execute,
    }
    agent_service.AgentManager.get_instance = staticmethod(lambda: FakeManager())
    agent_service.HistoryService.save_message = staticmethod(fake_save_message)
    agent_service.HistoryService.get_context_messages = staticmethod(fake_get_context)
    agent_service.HistoryService.check_and_generate_summary = staticmethod(noop_summary)
    agent_service.orchestrator.execute = fake_execute
    try:
        frames = [frame async for frame in agent_service.chat_stream("s-test", "午餐花了25元")]
    finally:
        agent_service.AgentManager.get_instance = originals["get_instance"]
        agent_service.HistoryService.save_message = originals["save_message"]
        agent_service.HistoryService.get_context_messages = originals["get_context"]
        agent_service.HistoryService.check_and_generate_summary = originals["summary"]
        agent_service.orchestrator.execute = originals["execute"]

    text = "".join(frames)
    # 基础帧
    assert text.startswith(": heartbeat"), text[:40]
    assert text.rstrip().endswith("data: [DONE]")
    # 派发期间下发了子 Agent 事件
    assert '"type": "agent_event"' in text
    assert '"event": "start"' in text and '"event": "done"' in text
    # 用户能看到主 Agent 的两段文字（派发前的铺垫 + 最终回复）
    assert "这就去记" in text and "记好" in text

    # 落库：user 一条 + assistant 一条（含派发记录）
    roles = [m["role"] for m in saved]
    assert roles == ["user", "assistant"], roles
    assert "记好" in saved[1]["content"]
    assert saved[1]["tool_calls"] and saved[1]["tool_calls"][0]["function"]["name"] == "delegate_to_bookkeeping"
    print("✅ 7. chat_stream 端到端（派发 → 事件 → 回复 → 落库）正常")


def test_prompt_and_tool_scope() -> None:
    """主 Agent 提示词含花名册；子 Agent 工具集互不越界"""
    prompt = build_master_system_prompt({
        "name": "小仓鼠",
        "personality": "亲切",
        "system_prompt": None,
    })
    assert "小仓鼠" in prompt
    assert "delegate_to_bookkeeping" in prompt
    assert "delegate_to_inventory" in prompt
    assert "分派规则" in prompt

    bookkeeping_names = {t["function"]["name"] for t in BookkeepingAgent.tools}
    inventory_names = {t["function"]["name"] for t in InventoryAgent.tools}

    assert bookkeeping_names == {"add_expense", "check_expense", "list_ledgers"}
    assert inventory_names == {
        "add_inventory", "consume_inventory", "check_inventory", "inventory_type", "complete_event",
    }
    assert not (bookkeeping_names & inventory_names), "两个子 Agent 的工具不应重叠"
    print("✅ 6. 提示词花名册 + 工具作用域隔离正常")


async def test_per_agent_provider_dispatch() -> None:
    """每个子 Agent 应拿到自己绑定的 provider，未绑定的回退主 Agent 的 provider"""
    bookkeeping = FakeDelegate("bookkeeping", "📒 记账专家")
    inventory = FakeDelegate("inventory", "📦 库存专家")
    table = {a.delegate_tool_name: a for a in (bookkeeping, inventory)}

    master_provider = FakeProvider([])
    sub_providers = {"bookkeeping": FakeProvider([])}  # 只有记账绑定了独立模型

    original = orch_module.resolve_delegate_tool
    orch_module.resolve_delegate_tool = lambda name: table.get(name)  # type: ignore[assignment]
    try:
        tool_calls = [
            ToolCallResult(id="p1", name="delegate_to_bookkeeping",
                           arguments={"task": "记录支出 60 元"}),
            ToolCallResult(id="p2", name="delegate_to_inventory",
                           arguments={"task": "牛奶入库 1 箱"}),
        ]
        await Orchestrator().execute(
            tool_calls, provider=master_provider,
            sub_providers=sub_providers,
        )
    finally:
        orch_module.resolve_delegate_tool = original  # type: ignore[assignment]

    # 记账拿到自己绑定的 provider，库存回退主 Agent 的 provider
    assert bookkeeping.providers == [sub_providers["bookkeeping"]]
    assert inventory.providers == [master_provider]
    print("✅ 7. 多模型分发：绑定子 Agent 用独立 provider，未绑定回退主模型")


async def main() -> None:
    await test_subagent_loop()
    await test_subagent_unknown_tool()
    await test_subagent_provider_error()
    await test_orchestrator_parallel()
    await test_orchestrator_unknown_tool_and_empty_task()
    test_prompt_and_tool_scope()
    await test_per_agent_provider_dispatch()
    await test_chat_stream_end_to_end()
    print("\n🎉 全部通过")


if __name__ == "__main__":
    asyncio.run(main())
