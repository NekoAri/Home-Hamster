"""
账本管理路由
提供账本的增删查改 RESTful API，支持多账本分账管理
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models import LedgerCreate, LedgerUpdate, LedgerResponse, LedgerWithStatsResponse
from app.services import crud
from app.database import get_pool

router = APIRouter(prefix="/api/ledgers", tags=["账本管理"])


@router.post("", response_model=LedgerResponse, summary="创建账本")
async def create_ledger(ledger: LedgerCreate):
    """创建一个新的账本"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.create_ledger(
            conn,
            name=ledger.name,
            icon=ledger.icon,
            color=ledger.color,
            description=ledger.description,
            is_default=ledger.is_default,
            sort_order=ledger.sort_order,
        )
        return record


@router.get("", summary="查询账本列表")
async def list_ledgers(
    with_stats: bool = Query(False, description="是否包含统计信息（记录数、总支出、总收入）"),
):
    """查询所有账本，可选包含统计信息"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.list_ledgers(conn, include_stats=with_stats)


@router.get("/{ledger_id}", response_model=LedgerResponse, summary="查询单个账本")
async def get_ledger(ledger_id: int):
    """根据 ID 查询账本"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.get_ledger(conn, ledger_id)
        if not record:
            raise HTTPException(status_code=404, detail="账本不存在")
        return record


@router.put("/{ledger_id}", response_model=LedgerResponse, summary="更新账本")
async def update_ledger(ledger_id: int, ledger: LedgerUpdate):
    """更新账本信息"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.update_ledger(conn, ledger_id, **ledger.model_dump())
        if not record:
            raise HTTPException(status_code=404, detail="账本不存在")
        return record


@router.delete("/{ledger_id}", summary="删除账本")
async def delete_ledger(ledger_id: int):
    """删除账本（不允许删除默认账本或含有记录的账本）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_ledger(conn, ledger_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="无法删除：账本是默认账本或仍有账目记录关联"
            )
        return {"message": "删除成功", "id": ledger_id}
