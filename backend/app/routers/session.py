"""
对话会话管理路由

提供会话的创建、列表、删除、历史消息查询等 API
"""

from fastapi import APIRouter, HTTPException
from app.models import SessionCreateRequest, SessionUpdateRequest
from app.services.history_service import HistoryService

router = APIRouter(prefix="/api/sessions", tags=["对话会话管理"])


@router.post("")
async def create_session(request: SessionCreateRequest):
    """
    创建新的对话会话

    前端在以下场景调用：
    - 用户首次打开对话页面
    - 用户点击"新对话"按钮
    """
    session = await HistoryService.create_session(
        user_id=request.user_id,
        title=request.title,
    )
    return session


@router.get("")
async def list_sessions(user_id: str = "default"):
    """
    列出用户的所有对话会话（按最近更新排序）

    返回每个会话的基本信息和最后一条消息预览
    """
    sessions = await HistoryService.list_sessions(user_id=user_id)
    return sessions


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    session = await HistoryService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话的全部消息（用于前端加载历史对话）"""
    session = await HistoryService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await HistoryService.get_messages(session_id)
    return {"session": session, "messages": messages}


@router.put("/{session_id}")
async def update_session(session_id: str, request: SessionUpdateRequest):
    """更新会话标题"""
    session = await HistoryService.update_session_title(session_id, request.title or "")
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话及其所有消息"""
    success = await HistoryService.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "会话已删除"}
