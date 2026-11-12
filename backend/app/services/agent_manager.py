"""
HomeHamster 全局 Agent 管理器（单例模式）

核心改进：
- 全局唯一 Agent 实例，避免每次请求重新加载配置和创建 provider
- 缓存 LLM provider、系统提示词、Agent 人设，减少数据库查询
- 支持热重载：当用户在前端修改 LLM 或 Agent 配置时，自动刷新缓存
- 线程安全（asyncio 单线程模型，无需锁）

使用方式：
    manager = AgentManager.get_instance()
    await manager.initialize()          # 应用启动时初始化
    provider = await manager.get_provider()  # 获取缓存的 provider
    manager.reload()                    # 配置变更时热重载
"""

import logging
from typing import Optional

from app.database import get_pool
from app.services import crud
from app.services.llm_provider import (
    LLMConfig,
    LLMProvider,
    create_provider,
)

logger = logging.getLogger(__name__)


class AgentManager:
    """
    全局 Agent 管理器（单例）

    职责：
    1. 从数据库加载并缓存 Agent 人设配置和 LLM 配置
    2. 创建并缓存 LLM provider 实例（避免每次请求重建 HTTP 客户端）
    3. 构建并缓存系统提示词
    4. 提供 reload() 方法，在配置变更时刷新缓存
    """

    _instance: Optional["AgentManager"] = None

    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止 __init__ 被多次调用重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # 缓存的配置和实例
        self._provider: Optional[LLMProvider] = None      # 主 Agent 的 provider
        self._sub_providers: dict[str, LLMProvider] = {}  # 子 Agent key -> provider（未绑定的子 Agent 回退主 Agent）
        self._agent_config: Optional[dict] = None
        self._llm_config: Optional[LLMConfig] = None
        self._model_bindings: dict[str, int] = {}         # agent_key -> llm_config_id（含 master）
        self._system_prompt: str = ""
        self._is_loaded: bool = False

    # ============================================================
    # 类方法：获取单例实例
    # ============================================================

    @classmethod
    def get_instance(cls) -> "AgentManager":
        """获取全局唯一的 AgentManager 实例"""
        return cls()

    # ============================================================
    # 初始化与热重载
    # ============================================================

    async def initialize(self) -> None:
        """
        初始化：从数据库加载配置，创建 provider
        在应用启动时调用（lifespan）
        """
        await self._load_config()
        logger.info("🐹 AgentManager 初始化完成")

    async def reload(self) -> None:
        """
        热重载：重新加载配置
        当用户在前端修改 LLM 或 Agent 配置后调用
        """
        logger.info("🔄 AgentManager 热重载中...")
        await self._load_config()
        logger.info("✅ AgentManager 热重载完成")

    async def _load_config(self) -> None:
        """从数据库加载 Agent 人设和 LLM 配置，创建 provider"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 加载激活的 Agent 人设
            agent_config = await crud.get_active_agent_config(conn)
            if agent_config:
                self._agent_config = agent_config
            else:
                self._agent_config = self._get_default_agent_config()

            # 加载 LLM 配置（优先 Agent 配置中指定的，否则用激活的）
            llm_config_dict = None
            llm_config_id = self._agent_config.get("llm_config_id")
            if llm_config_id:
                llm_config_dict = await crud.get_llm_config(conn, llm_config_id)
            if not llm_config_dict:
                llm_config_dict = await crud.get_active_llm_config(conn)

            if llm_config_dict:
                self._llm_config = self._dict_to_llm_config(llm_config_dict)
                # 用 Agent 配置的温度覆盖 LLM 配置的温度
                self._llm_config.temperature = float(
                    self._agent_config.get("temperature", 0.7)
                )
                try:
                    self._provider = create_provider(self._llm_config)
                except ValueError as e:
                    logger.error(f"创建 LLM provider 失败: {e}")
                    self._provider = None
            else:
                self._llm_config = None
                self._provider = None
                logger.warning("⚠️ 未找到激活的 LLM 配置")

            # 构建系统提示词
            self._system_prompt = self._build_system_prompt(self._agent_config)

            # ---- 加载各 Agent 的模型绑定（主从架构支持每个 Agent 用不同模型）----
            await crud.ensure_agent_model_bindings_table(conn)
            self._model_bindings = await crud.list_agent_model_bindings(conn)
            self._sub_providers = await self._load_sub_providers(
                conn, self._provider, self._model_bindings
            )

        self._is_loaded = True

    async def _load_sub_providers(
        self,
        conn,
        master_provider: Optional[LLMProvider],
        bindings: dict[str, int],
    ) -> dict[str, LLMProvider]:
        """
        按绑定表为每个子 Agent 构建独立 provider。

        - 绑定的 llm_config_id 存在且有效 → 创建独立 provider
        - 绑定失效（配置被删）或未绑定 → 回退主 Agent 的 provider
        """
        from app.services.agents.registry import list_agents

        sub_providers: dict[str, LLMProvider] = {}
        for agent in list_agents():
            binding_id = bindings.get(agent.key)
            provider = master_provider
            if binding_id:
                llm_dict = await crud.get_llm_config(conn, binding_id)
                if llm_dict:
                    try:
                        provider = create_provider(self._dict_to_llm_config(llm_dict))
                    except ValueError as e:
                        logger.error(f"子 Agent {agent.key} 的 provider 创建失败: {e}")
                        provider = master_provider
                else:
                    logger.warning(f"子 Agent {agent.key} 绑定的 LLM 配置 {binding_id} 不存在，回退主模型")
            sub_providers[agent.key] = provider
            bound = f"独立模型 {provider.config.model_name}" if provider is not master_provider else "主 Agent 模型"
            logger.info(f"🧩 子 Agent {agent.label} → {bound}")
        return sub_providers

    # ============================================================
    # 对外接口
    # ============================================================

    async def get_provider(self) -> Optional[LLMProvider]:
        """获取缓存的 LLM provider 实例"""
        if not self._is_loaded:
            await self.initialize()
        return self._provider

    def get_system_prompt(self) -> str:
        """获取缓存的系统提示词"""
        return self._system_prompt

    def get_agent_info(self) -> dict:
        """获取 Agent 人设信息（名字、头像等）"""
        return self._agent_config or self._get_default_agent_config()

    def get_llm_config(self) -> Optional[LLMConfig]:
        """获取当前（主 Agent）LLM 配置"""
        return self._llm_config

    def get_sub_providers(self) -> dict[str, LLMProvider]:
        """获取各子 Agent 的 provider 映射（未绑定者与主 Agent 共用）"""
        return dict(self._sub_providers)

    def get_model_bindings(self) -> dict[str, int]:
        """获取各 Agent 的模型绑定（agent_key -> llm_config_id）"""
        return dict(self._model_bindings)

    def is_ready(self) -> bool:
        """检查 Agent 是否已配置就绪（有可用的 provider）"""
        return self._provider is not None

    # ============================================================
    # 内部工具方法
    # ============================================================

    def _get_default_agent_config(self) -> dict:
        """默认 Agent 配置（数据库中无配置时使用）"""
        return {
            "name": "HomeHamster",
            "avatar": "🐹",
            "personality": "",
            "system_prompt": None,
            "temperature": 0.7,
        }

    def _build_system_prompt(self, agent_config: dict) -> str:
        """
        构建主 Agent 的系统提示词。

        主从架构下，提示词由编排器统一生成：人设 + 子 Agent 花名册 + 分派规则。
        用户自定义了 system_prompt 时，它会作为「人设」部分被保留，
        编排规则仍会自动附加（否则主 Agent 就不知道要派活）。
        """
        from app.services.orchestrator import build_master_system_prompt

        return build_master_system_prompt(agent_config)

    def _dict_to_llm_config(self, d: dict) -> LLMConfig:
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
