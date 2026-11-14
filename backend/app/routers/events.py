"""
事件路由（P2 提醒闭环）

- GET    /api/events                事件列表（默认待处理）
- POST   /api/events/{id}/complete  完成
- POST   /api/events/{id}/snooze    稍后（snooze，默认 24h）
- POST   /api/events/{id}/dismiss   忽略
- POST   /api/events/sync           手动同步库存事件（调试/验收用）
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_pool
from app.services import crud
from app.services.event_service import (
    complete_event,
    dismiss_event,
    snooze_event,
    sync_inventory_events,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["事件提醒"])


class SnoozeRequest(BaseModel):
    hours: float = Field(24.0, gt=0, le=24 * 30, description="顺延小时数")


@router.get("", summary="事件列表")
async def list_events(
    status: str = Query("pending", description="事件状态: pending/done/snoozed/dismissed，为空查全部"),
    kind: str = Query("", description="事件类型筛选，为空查全部"),
    limit: int = Query(50, ge=1, le=100),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        events = await crud.list_events(
            conn, status=status or None, kind=kind or None, limit=limit
        )
    return events


@router.post("/sync", summary="手动同步库存事件")
async def sync_events():
    """扫描库存生成/更新/自动解决事件（提醒扫描 job 每半小时也会自动跑）"""
    return await sync_inventory_events()


@router.post("/{event_id}/complete", summary="标记完成")
async def mark_complete(event_id: int):
    result = await complete_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="事件不存在")
    return result


@router.post("/{event_id}/snooze", summary="稍后提醒")
async def mark_snooze(event_id: int, payload: SnoozeRequest | None = None):
    hours = payload.hours if payload else 24.0
    result = await snooze_event(event_id, hours=hours)
    if not result:
        raise HTTPException(status_code=404, detail="事件不存在")
    return result


@router.post("/{event_id}/dismiss", summary="忽略")
async def mark_dismiss(event_id: int):
    result = await dismiss_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="事件不存在")
    return result
