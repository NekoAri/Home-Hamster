"""
通知适配器模块

设计约定（P0 基础设施）：
- 只定义 Notifier 协议 + 具体渠道实现，不做多渠道路由、不做通知模板引擎。
- 渠道配置存 notify_channels 表（type / config JSONB / enabled）。
- 同一时间最多启用一个渠道（get_enabled_notify_channel）。
- 所有发送失败都不抛异常，只返回 False 并记日志——通知失败不能拖垮主流程。

level 约定：info（日常）/ warning（需要留意）/ urgent（紧急），渠道实现可自行映射。
"""

import logging
from typing import Protocol, runtime_checkable

import httpx

from app.database import get_pool
from app.services import crud

logger = logging.getLogger(__name__)

# 支持的渠道类型（与 notify_channels.type 对应）
SUPPORTED_CHANNEL_TYPES = ("bark", "console")


# ============================================================
# 协议定义
# ============================================================

@runtime_checkable
class Notifier(Protocol):
    """通知渠道协议：所有渠道实现此接口"""

    async def send(self, title: str, body: str, level: str = "info") -> bool:
        """发送一条通知，成功返回 True，失败返回 False（不抛异常）"""
        ...


# ============================================================
# ConsoleNotifier —— 本地调试用，打到日志
# ============================================================

class ConsoleNotifier:
    """把通知打到本地日志，用于没有真实渠道时的调试"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def send(self, title: str, body: str, level: str = "info") -> bool:
        logger.info(f"[ConsoleNotifier][{level}] {title}\n{body}")
        return True


# ============================================================
# BarkNotifier —— iOS Bark 推送，配置最简单（server + device_key）
# ============================================================

class BarkNotifier:
    """
    Bark 推送（iOS App）。

    config 示例：
        {"server": "https://api.day.app", "device_key": "xxxxxx"}
    server 可省略，默认官方服务；自建 Bark 服务填自己的地址。
    """

    DEFAULT_SERVER = "https://api.day.app"
    DEFAULT_GROUP = "HomeHamster"

    def __init__(self, config: dict):
        self.server = (config.get("server") or self.DEFAULT_SERVER).rstrip("/")
        self.device_key = config.get("device_key") or ""
        if not self.device_key:
            raise ValueError("Bark 渠道缺少 device_key 配置")

    async def send(self, title: str, body: str, level: str = "info") -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.server}/push",
                    json={
                        "device_key": self.device_key,
                        "title": title,
                        "body": body,
                        "group": self.DEFAULT_GROUP,
                        # Bark 仅支持 active / timeSensitive / passive 三档
                        "level": {
                            "info": "active",
                            "warning": "timeSensitive",
                            "urgent": "timeSensitive",
                        }.get(level, "active"),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 200:
                    logger.warning(f"Bark 推送返回异常: {data}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Bark 推送失败: {e}")
            return False


# ============================================================
# 渠道工厂：从数据库读启用的渠道配置并构建 Notifier
# ============================================================

async def build_notifier(channel: dict) -> Notifier:
    """根据渠道记录构建 Notifier 实例"""
    type_ = channel.get("type", "")
    config = channel.get("config") or {}
    if type_ == "bark":
        return BarkNotifier(config)
    if type_ == "console":
        return ConsoleNotifier(config)
    raise ValueError(f"不支持的通知渠道类型: {type_}")


async def get_notifier() -> Notifier | None:
    """
    获取当前启用的通知渠道实例。
    没有启用渠道或构建失败时返回 None（调用方自行决定降级行为）。
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            channel = await crud.get_enabled_notify_channel(conn)
    except Exception as e:
        logger.error(f"读取通知渠道配置失败: {e}")
        return None
    if not channel:
        return None
    try:
        return await build_notifier(channel)
    except Exception as e:
        logger.error(f"构建通知渠道 {channel.get('type')} 失败: {e}")
        return None
