"""
记忆管理路由（P3）

「记忆不可见 = 不可信」——所有长期记忆在此对用户可见，支持删除与纠正。
- GET    /api/memories       记忆列表
- PUT    /api/memories/{id}  纠正记忆内容（纠正后向量置空，避免过期语义）
- DELETE /api/memories/{id}  删除记忆
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_pool
from app.services import crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memories", tags=["记忆管理"])


class MemoryUpdate(BaseModel):
    """纠正记忆内容"""
    content: str = Field(..., min_length=2, max_length=500, description="纠正后的记忆内容")


@router.get("", summary="记忆列表")
async def list_memories(
    memory_type: str = Query("", description="类型筛选: preference/fact/habit，为空查全部"),
    limit: int = Query(200, ge=1, le=500),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        memories = await crud.list_memories(
            conn, "default", memory_type=memory_type or None, limit=limit
        )
    return memories


@router.put("/{memory_id}", summary="纠正记忆")
async def update_memory(memory_id: int, payload: MemoryUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await crud.update_memory_content(conn, memory_id, payload.content.strip())
    if not result:
        raise HTTPException(status_code=404, detail="记忆不存在")
    logger.info(f"🧠 记忆 {memory_id} 已纠正")
    return {k: v for k, v in result.items() if k != "embedding"}


@router.delete("/{memory_id}", summary="删除记忆")
async def delete_memory(memory_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        ok = await crud.delete_memory(conn, memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"message": "已删除"}
