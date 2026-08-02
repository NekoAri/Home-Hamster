"""
物品类别管理路由
"""

from fastapi import APIRouter, HTTPException, Query
from app.models import CategoryCreate, CategoryUpdate, CategoryResponse
from app.services import crud
from app.database import get_pool

router = APIRouter(prefix="/api/categories", tags=["物品类别管理"])


@router.post("", response_model=CategoryResponse, summary="创建物品类别")
async def create_category(category: CategoryCreate):
    """新增物品类别"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.create_category(
            conn,
            name=category.name,
            code=category.code,
            description=category.description,
        )


@router.get("", response_model=list[CategoryResponse], summary="查询所有物品类别")
async def list_categories():
    """查询所有物品类别"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.list_categories(conn)


@router.get("/{category_id}", response_model=CategoryResponse, summary="查询单个类别")
async def get_category(category_id: int):
    """根据 ID 查询物品类别"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.get_category(conn, category_id)
        if not record:
            raise HTTPException(status_code=404, detail="类别不存在")
        return record


@router.put("/{category_id}", response_model=CategoryResponse, summary="更新物品类别")
async def update_category(category_id: int, category: CategoryUpdate):
    """更新物品类别"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.update_category(conn, category_id, **category.model_dump())
        if not record:
            raise HTTPException(status_code=404, detail="类别不存在")
        return record


@router.delete("/{category_id}", summary="删除物品类别")
async def delete_category(category_id: int):
    """删除物品类别"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_category(conn, category_id)
        if not success:
            raise HTTPException(status_code=404, detail="类别不存在")
        return {"message": "删除成功", "id": category_id}
