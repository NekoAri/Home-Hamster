"""
Agent 对话路由
提供 SSE 流式对话接口，支持 Function Calling
自动从数据库加载当前激活的 LLM 配置和 Agent 人设配置
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

    接收用户的对话消息，自动加载当前激活的 LLM 配置和 Agent 人设配置，
    通过对应供应商的 API 进行处理，支持 Function Calling 调用家庭管理工具，
    最终以 SSE 格式流式返回响应。

    请求体格式：
    ```json
    {
        "messages": [
            {"role": "user", "content": "帮我记一笔，午餐花了25元"}
        ],
        "user_id": "default"
    }
    ```

    响应格式：SSE 流，每条消息格式为 `data: {"content": "token"}\\n\\n`

    配置说明：
    - LLM 配置通过 `POST /api/configs/llm` 创建并激活
    - Agent 人设通过 `POST /api/configs/agent` 创建并激活
    - 未配置 LLM 时会返回提示信息
    """

    # 将 Pydantic 模型转为 LLM 所需的消息格式
    messages = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]

    return StreamingResponse(
        chat_stream(messages, request.user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，确保实时流式输出
        },
    )
