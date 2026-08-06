"""
Agent 对话路由（v3 - 全局实例 + 历史管理）

改进：
- 使用 session_id + content 替代全量 messages，避免长对话阻塞
- Agent 实例全局复用，无需每次请求重新加载配置
- 历史消息由后端管理，前端只需发送最新消息
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.agent_service import chat_stream

router = APIRouter(prefix="/api/agent", tags=["Agent 对话"])


@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """
    Agent 对话接口（SSE 流式输出）

    v3 改进：
    - 请求体只需 session_id + content，不再传全量 messages
    - 后端从数据库加载对话历史，应用滑动窗口 + 摘要压缩
    - 使用全局缓存的 Agent provider 实例

    请求体格式：
    ```json
    {
        "session_id": "uuid-string",
        "content": "帮我记一笔，午餐花了25元",
        "user_id": "default"
    }
    ```

    响应格式：SSE 流，每条消息格式为 `data: {"content": "token"}\\n\\n`
    """
    return StreamingResponse(
        chat_stream(request.session_id, request.content, request.user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
