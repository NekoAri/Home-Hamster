"""
物品仓储管理路由
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models import InventoryCreate, InventoryUpdate, InventoryResponse
from app.services import crud
from app.database import get_pool

router = APIRouter(prefix="/api/inventory", tags=["物品仓储管理"])


@router.post("", response_model=InventoryResponse, summary="创建物品库存")
async def create_inventory(item: InventoryCreate):
    """添加一条物品库存记录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.create_inventory(
            conn,
            name=item.name,
            barcode=item.barcode,
            category_id=item.category_id,
            quantity=item.quantity,
            unit=item.unit,
            location=item.location,
            expiry_date=item.expiry_date,
            custom_attrs=item.custom_attrs,
        )


@router.get("", response_model=list[InventoryResponse], summary="查询物品列表")
async def list_inventory(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    name: Optional[str] = Query(None, description="物品名称（模糊搜索）"),
    category_id: Optional[int] = Query(None, description="类别 ID"),
    location: Optional[str] = Query(None, description="存放位置（模糊搜索）"),
    barcode: Optional[str] = Query(None, description="物品条码"),
):
    """查询物品库存列表，支持模糊搜索和筛选"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.list_inventory(
            conn, limit=limit, offset=offset,
            name=name, category_id=category_id,
            location=location, barcode=barcode,
        )


@router.get("/{inventory_id}", response_model=InventoryResponse, summary="查询单个物品")
async def get_inventory(inventory_id: int):
    """根据 ID 查询单个物品"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.get_inventory(conn, inventory_id)
        if not record:
            raise HTTPException(status_code=404, detail="物品不存在")
        return record


@router.put("/{inventory_id}", response_model=InventoryResponse, summary="更新物品库存")
async def update_inventory(inventory_id: int, item: InventoryUpdate):
    """更新物品库存记录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.update_inventory(conn, inventory_id, **item.model_dump())
        if not record:
            raise HTTPException(status_code=404, detail="物品不存在")
        return record


@router.delete("/{inventory_id}", summary="删除物品库存")
async def delete_inventory(inventory_id: int):
    """删除物品库存记录"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_inventory(conn, inventory_id)
        if not success:
            raise HTTPException(status_code=404, detail="物品不存在")
        return {"message": "删除成功", "id": inventory_id}
