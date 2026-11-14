"""
每日早报路由

- GET  /api/reports           历史早报列表（前端「今日简报」读同一份数据）
- GET  /api/reports/latest    今天/最近一条早报
- POST /api/reports/send-now  手动立即生成并发送（不受同日幂等限制）
- GET/PUT /api/reports/settings  早报开关与发送时间（变更后自动重挂定时任务）
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import get_pool
from app.services import crud
from app.services.morning_report import generate_and_send, load_settings, save_settings
from app.services.scheduler import reschedule_morning_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["每日早报"])


class MorningReportSettings(BaseModel):
    """早报设置"""
    enabled: bool = Field(True, description="是否启用每日早报")
    hour: int = Field(8, ge=0, le=23, description="发送时间-小时（Asia/Shanghai）")
    minute: int = Field(0, ge=0, le=59, description="发送时间-分钟")


@router.get("", summary="历史早报列表")
async def list_reports(limit: int = 30):
    """按日期倒序返回历史早报（含模板版/润色版正文与原始数据）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        reports = await crud.list_daily_reports(conn, limit=min(limit, 100))
    return reports


@router.get("/latest", summary="最近一条早报")
async def latest_report():
    """返回今天的早报（没有则返回最近一条），前端「今日简报」首屏用"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await crud.list_daily_reports(conn, limit=1)
    return rows[0] if rows else None


@router.post("/send-now", summary="手动立即发送早报")
async def send_now():
    """
    立即生成并发送今天的早报（force，不做同日幂等跳过，便于验收测试）。
    LLM 不可用时自动发送模板版。
    """
    try:
        result = await generate_and_send(force=True, trigger="manual")
        return result
    except Exception as e:
        logger.error(f"手动发送早报失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送失败: {e}")


@router.get("/settings", response_model=MorningReportSettings, summary="读取早报设置")
async def get_report_settings():
    settings = await load_settings()
    return MorningReportSettings(**settings)


@router.put("/settings", response_model=MorningReportSettings, summary="保存早报设置")
async def update_report_settings(payload: MorningReportSettings):
    """
    保存早报开关与发送时间，并立即重挂定时任务（无需重启后端）。
    """
    saved = await save_settings(payload.model_dump())
    try:
        await reschedule_morning_report()
    except Exception as e:
        # 重挂失败不影响设置保存本身
        logger.error(f"重挂早报任务失败: {e}")
    return MorningReportSettings(**saved)
