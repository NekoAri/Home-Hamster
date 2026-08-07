"""
HomeHamster 数据库异步连接模块
使用 asyncpg 创建连接池，支持高并发异步数据库操作
"""

import asyncpg
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# 全局连接池实例（在应用启动时创建，关闭时销毁）
_pool: asyncpg.Pool | None = None


async def init_db_pool() -> asyncpg.Pool:
    """
    初始化 asyncpg 连接池
    在 FastAPI lifespan 中调用，应用启动时创建连接池

    注意：针对中文 Windows 环境的 PostgreSQL 服务器（GBK 编码），
    显式设置 client_encoding=utf8 和 lc_messages=C 避免编码问题。
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_dsn,
            min_size=5,          # 最小连接数
            max_size=20,         # 最大连接数
            command_timeout=60,  # 命令超时时间（秒）
            ssl=False,           # 禁用 SSL（服务器未开启）
            init=register_types, # 初始化时注册自定义类型（如 pgvector）
            server_settings={
                "client_encoding": "utf8",
                "lc_messages": "C",
            },
        )
        logger.info("数据库连接池已创建")
    return _pool


async def register_types(conn: asyncpg.Connection):
    """
    为每个连接注册自定义类型：
    1. pgvector 扩展类型（向量检索）
    2. JSON/JSONB 编解码器（让 asyncpg 返回 Python dict 而非 str）
    """
    import json

    # 1. 注册 pgvector 扩展类型
    from pgvector.asyncpg import register_vector
    await register_vector(conn)

    # 2. 注册 JSON/JSONB 编解码器
    # asyncpg 默认将 JSONB 列返回为字符串，这里注册编解码器使其返回 Python dict/list
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def get_pool() -> asyncpg.Pool:
    """获取数据库连接池"""
    if _pool is None:
        await init_db_pool()
    return _pool


async def close_db_pool():
    """关闭数据库连接池，在应用关闭时调用"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("数据库连接池已关闭")


async def get_conn() -> asyncpg.Connection:
    """
    获取数据库连接（上下文管理器）
    在路由中使用：`async with get_conn() as conn:`
    """
    pool = await get_pool()
    return pool.acquire()
