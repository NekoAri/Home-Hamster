"""
账目管理路由
提供账目的增删查改 RESTful API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from app.models import AccountCreate, AccountUpdate, AccountResponse
from app.services import crud
from app.database import get_pool

router = APIRouter(prefix="/api/accounts", tags=["账目管理"])


@router.post("", response_model=AccountResponse, summary="创建账目")
async def create_account(account: AccountCreate):
    """添加一条账目记录（支出或收入）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.create_account(
            conn,
            amount=account.amount,
            category=account.category,
            type=account.type,
            occurred_at=account.occurred_at,
            note=account.note,
        )
        return record


@router.get("", response_model=list[AccountResponse], summary="查询账目列表")
async def list_accounts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None, description="按分类筛选"),
    type: Optional[str] = Query(None, description="按类型筛选: expense/income"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
):
    """查询账目列表，支持按分类、类型、时间范围筛选"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.list_accounts(
            conn, limit=limit, offset=offset,
            category=category, type=type,
            start_date=start_date, end_date=end_date,
        )


@router.get("/{account_id}", response_model=AccountResponse, summary="查询单条账目")
async def get_account(account_id: int):
    """根据 ID 查询单条账目"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.get_account(conn, account_id)
        if not record:
            raise HTTPException(status_code=404, detail="账目不存在")
        return record


@router.put("/{account_id}", response_model=AccountResponse, summary="更新账目")
async def update_account(account_id: int, account: AccountUpdate):
    """更新账目记录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.update_account(conn, account_id, **account.model_dump())
        if not record:
            raise HTTPException(status_code=404, detail="账目不存在")
        return record


@router.delete("/{account_id}", summary="删除账目")
async def delete_account(account_id: int):
    """删除账目记录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_account(conn, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="账目不存在")
        return {"message": "删除成功", "id": account_id}
