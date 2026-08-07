"""
HomeHamster 家庭管理 Agent - FastAPI 应用入口
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db_pool, close_db_pool
from app.services.agent_manager import AgentManager
from app.routers import agent, account, inventory, category, config, summary, session, ledger

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时创建连接池，关闭时释放"""
    # ---- 启动 ----
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 正在启动...")
    await init_db_pool()
    logger.info("✅ 数据库连接池已就绪")

    # 初始化全局 Agent 实例（加载配置 + 创建 provider）
    await AgentManager.get_instance().initialize()
    logger.info("🐹 全局 Agent 实例已就绪")

    logger.info(f"🌐 服务地址: http://localhost:8000")
    logger.info(f"📖 API 文档: http://localhost:8000/docs")

    yield

    # ---- 关闭 ----
    await close_db_pool()
    logger.info(f"👋 {settings.APP_NAME} 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="家庭管理 Agent - 账目管理、物品仓储、智能建议",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS 中间件配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent.router)       # Agent 对话（SSE 流式）
app.include_router(session.router)     # 对话会话管理 [v3 新增]
app.include_router(config.router)     # 配置管理（LLM + Agent 人设，变更时热重载）
app.include_router(account.router)     # 账目 CRUD
app.include_router(ledger.router)      # 账本 CRUD（多账本分账管理）
app.include_router(inventory.router)   # 物品仓储 CRUD
app.include_router(category.router)    # 物品类别 CRUD
app.include_router(summary.router)     # 统计概览（仪表盘数据）


@app.get("/", tags=["健康检查"])
async def root():
    """根路径 - 健康检查"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
