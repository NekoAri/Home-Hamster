"""
通知渠道管理路由

提供通知渠道配置的查询 / 保存 / 测试发送。
渠道类型当前支持: bark（iOS Bark 推送）、console（本地调试，打到日志）。
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import NotifyChannelSave, NotifyChannelResponse
from app.database import get_pool
from app.services import crud
from app.services.notifier import SUPPORTED_CHANNEL_TYPES, get_notifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notify", tags=["通知渠道"])


@router.get("/channel", response_model=list[NotifyChannelResponse],
            summary="查询通知渠道配置")
async def list_channels():
    """查询所有通知渠道配置（含 device_key 明文，单机自用场景）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        channels = await crud.list_notify_channels(conn)
    return channels


@router.put("/channel", response_model=NotifyChannelResponse, summary="保存通知渠道配置")
async def save_channel(payload: NotifyChannelSave):
    """保存/更新通知渠道配置（同 type 只保留一条）"""
    if payload.type not in SUPPORTED_CHANNEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的渠道类型: {payload.type}（支持: {', '.join(SUPPORTED_CHANNEL_TYPES)}）",
        )
    pool = await get_pool()
    async with pool.acquire() as conn:
        channel = await crud.upsert_notify_channel(
            conn, payload.type, payload.name, payload.config, payload.enabled
        )
    if not channel:
        raise HTTPException(status_code=500, detail="保存通知渠道失败")
    return channel


@router.post("/test", summary="发送测试通知")
async def send_test_notification():
    """
    用当前启用的渠道发一条测试通知，验证配置是否正确。
    没有启用渠道时返回 ok=False 并说明原因。
    """
    notifier = await get_notifier()
    if notifier is None:
        return {"ok": False, "message": "没有已启用的通知渠道，请先在通知设置中配置并启用"}
    ok = await notifier.send("仓鼠管家测试", "通知渠道已打通，之后我会在这个时间叫你。", level="info")
    if ok:
        return {"ok": True, "message": "测试通知已发送，请查收"}
    return {"ok": False, "message": "发送失败，请检查渠道配置（如 device_key 是否正确）"}
