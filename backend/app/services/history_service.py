"""
HomeHamster 对话历史管理服务

核心机制：
1. **消息持久化**：所有对话消息存入数据库，不再依赖前端传全量上下文
2. **滑动窗口**：只取最近 N 条消息作为 LLM 上下文，避免 token 爆炸
3. **自动摘要**：当消息数超过阈值时，自动将较早的消息摘要化，减少 token 消耗
4. **多会话支持**：用户可以创建多个独立会话，各自维护历史

数据流：
  前端发送 { session_id, content } → 后端保存消息 → 加载窗口内历史 →
  构建 LLM 上下文 [system + summary + windowed_messages] → 调用 LLM →
  保存回复 → 检查是否需要生成摘要 → 流式返回
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator

from app.database import get_pool

logger = logging.getLogger(__name__)


class HistoryService:
    """
    对话历史管理服务

    配置项：
    - WINDOW_SIZE: 滑动窗口大小，保留最近 N 条消息（含 user + assistant + tool）
    - SUMMARY_THRESHOLD: 当消息总数超过此阈值时，触发摘要生成
    - MAX_SUMMARY_TOKENS: 摘要的最大 token 数估算
    """

    # 滑动窗口：保留最近 20 条消息发给 LLM
    WINDOW_SIZE = 20

    # 摘要阈值：消息总数超过 30 条时生成摘要
    SUMMARY_THRESHOLD = 30

    # 摘要中保留的早期消息条数（对这些消息生成摘要）
    SUMMARY_BATCH_SIZE = 15

    # ============================================================
    # 会话管理
    # ============================================================

    @staticmethod
    async def create_session(
        user_id: str = "default",
        title: Optional[str] = None,
    ) -> dict:
        """
        创建新的对话会话

        Args:
            user_id: 用户标识
            title: 会话标题（为空时自动生成）

        Returns:
            会话信息字典，包含 session_id
        """
        session_id = str(uuid.uuid4())
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_sessions (session_id, user_id, title)
                VALUES ($1, $2, COALESCE($3, '新对话'))
                RETURNING id, session_id, user_id, title, summary, message_count, created_at, updated_at
                """,
                session_id, user_id, title,
            )
            return dict(row)

    @staticmethod
    async def get_session(session_id: str) -> Optional[dict]:
        """获取会话信息"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, session_id, user_id, title, summary, message_count, is_archived, created_at, updated_at
                FROM chat_sessions WHERE session_id = $1
                """,
                session_id,
            )
            return dict(row) if row else None

    @staticmethod
    async def list_sessions(
        user_id: str = "default",
        limit: int = 50,
    ) -> list[dict]:
        """
        列出用户的所有会话（按最近更新排序）

        Returns:
            会话列表，每个会话包含基本信息和最后一条消息预览
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    s.id, s.session_id, s.user_id, s.title,
                    s.message_count, s.summary, s.created_at, s.updated_at,
                    (
                        SELECT content FROM chat_messages
                        WHERE session_id = s.session_id
                        ORDER BY created_at DESC LIMIT 1
                    ) AS last_message,
                    (
                        SELECT created_at FROM chat_messages
                        WHERE session_id = s.session_id
                        ORDER BY created_at DESC LIMIT 1
                    ) AS last_message_time
                FROM chat_sessions s
                WHERE s.user_id = $1 AND s.is_archived = FALSE
                ORDER BY s.updated_at DESC
                LIMIT $2
                """,
                user_id, limit,
            )
            return [dict(row) for row in rows]

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """删除会话及其所有消息（级联删除）"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chat_sessions WHERE session_id = $1",
                session_id,
            )
            return result.endswith("1")

    @staticmethod
    async def update_session_title(session_id: str, title: str) -> Optional[dict]:
        """更新会话标题"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE chat_sessions SET title = $2
                WHERE session_id = $1
                RETURNING id, session_id, title
                """,
                session_id, title,
            )
            return dict(row) if row else None

    # ============================================================
    # 消息持久化
    # ============================================================

    @staticmethod
    async def save_message(
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list[dict]] = None,
        tool_call_id: Optional[str] = None,
    ) -> dict:
        """
        保存一条对话消息到数据库

        Args:
            session_id: 会话 ID
            role: 消息角色 (user / assistant / tool)
            content: 消息内容
            tool_calls: 工具调用信息（assistant 消息可能携带）
            tool_call_id: 工具调用 ID（tool 角色消息）

        Returns:
            保存的消息记录
        """
        token_count = HistoryService._estimate_tokens(content)
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_messages (session_id, role, content, tool_calls, tool_call_id, token_count)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                RETURNING id, session_id, role, content, tool_calls, tool_call_id, token_count, created_at
                """,
                session_id, role, content,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                tool_call_id,
                token_count,
            )

            # 更新会话的消息计数和更新时间
            await conn.execute(
                """
                UPDATE chat_sessions
                SET message_count = message_count + 1, updated_at = NOW()
                WHERE session_id = $1
                """,
                session_id,
            )

            # 如果是第一条用户消息且会话标题还是默认的，自动更新标题
            if role == "user":
                await conn.execute(
                    """
                    UPDATE chat_sessions
                    SET title = LEFT($2, 50)
                    WHERE session_id = $1 AND title = '新对话' AND message_count = 1
                    """,
                    session_id, content,
                )

            return dict(row)

    @staticmethod
    async def get_messages(
        session_id: str,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        获取会话的全部消息（按时间正序）

        Args:
            session_id: 会话 ID
            limit: 限制返回条数（None 表示全部）

        Returns:
            消息列表
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            if limit:
                rows = await conn.fetch(
                    """
                    SELECT id, session_id, role, content, tool_calls, tool_call_id, token_count, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    session_id, limit,
                )
                # 反转为正序（旧→新）
                return list(reversed([dict(row) for row in rows]))
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, session_id, role, content, tool_calls, tool_call_id, token_count, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at
                    """,
                    session_id,
                )
                return [dict(row) for row in rows]

    # ============================================================
    # 上下文构建（核心：滑动窗口 + 摘要）
    # ============================================================

    @staticmethod
    async def get_context_messages(session_id: str) -> list[dict]:
        """
        获取用于 LLM 上下文的消息列表

        策略：
        1. 获取会话摘要（如有）→ 作为一条 system 消息插入
        2. 获取最近 WINDOW_SIZE 条消息 → 作为对话历史
        3. 返回 [摘要(如有)] + [窗口内消息]

        Returns:
            LLM 格式的消息列表（不含 system prompt，由 AgentManager 负责）
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 获取会话摘要
            session = await conn.fetchrow(
                "SELECT summary, message_count FROM chat_sessions WHERE session_id = $1",
                session_id,
            )
            if not session:
                return []

            messages = []

            # 如果有摘要，作为 system 备注插入
            summary = session.get("summary", "")
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"[以下是之前对话的摘要]\n{summary}\n[摘要结束，以下是最近对话]",
                })

            # 获取最近 WINDOW_SIZE 条消息（正序）
            rows = await conn.fetch(
                """
                SELECT role, content, tool_calls, tool_call_id
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                session_id, HistoryService.WINDOW_SIZE,
            )

            # 反转为正序（旧→新）
            window_messages = list(reversed([dict(row) for row in rows]))

            # 将数据库记录转换为 LLM 消息格式
            for msg in window_messages:
                role = msg["role"]
                content = msg["content"]

                if role == "tool":
                    # 工具结果消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "content": content,
                    })
                elif role == "assistant" and msg.get("tool_calls"):
                    # 带工具调用的 assistant 消息
                    tool_calls = msg["tool_calls"] if isinstance(msg["tool_calls"], list) else json.loads(msg["tool_calls"])
                    messages.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls,
                    })
                else:
                    messages.append({
                        "role": role,
                        "content": content,
                    })

            return messages

    @staticmethod
    async def check_and_generate_summary(
        session_id: str,
        provider=None,
    ) -> Optional[str]:
        """
        检查是否需要生成摘要，如果需要则生成

        当消息总数超过 SUMMARY_THRESHOLD 时，取最早的 SUMMARY_BATCH_SIZE 条消息
        生成摘要，然后删除这些消息（保留摘要），从而控制上下文长度

        Args:
            session_id: 会话 ID
            provider: LLM provider 实例（用于生成摘要）

        Returns:
            生成的摘要文本，如果未生成则返回 None
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            session = await conn.fetchrow(
                "SELECT message_count, summary FROM chat_sessions WHERE session_id = $1",
                session_id,
            )
            if not session:
                return None

            message_count = session["message_count"]
            if message_count < HistoryService.SUMMARY_THRESHOLD:
                return None

            # 获取最早的 SUMMARY_BATCH_SIZE 条消息
            old_messages = await conn.fetch(
                """
                SELECT role, content, created_at
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at
                LIMIT $2
                """,
                session_id, HistoryService.SUMMARY_BATCH_SIZE,
            )

            if not old_messages:
                return None

            # 构建摘要请求
            conversation_text = "\n".join(
                f"[{msg['role']}] {msg['content'][:200]}"
                for msg in old_messages
            )

            existing_summary = session.get("summary", "")
            summary_prompt = f"""请将以下对话历史浓缩为一段简短的摘要（不超过 300 字），保留关键信息（用户的需求、已完成的操作、重要的数据点）。

{"已有摘要：" + existing_summary + chr(10) if existing_summary else ""}
需要汇总的对话：
{conversation_text}

请直接输出摘要内容，不要加额外格式："""

            summary_text = None

            # 尝试使用 LLM 生成摘要
            if provider:
                try:
                    summary_messages = [{"role": "user", "content": summary_prompt}]
                    collected = []
                    async for token in provider.chat_stream(summary_messages):
                        collected.append(token)
                    summary_text = "".join(collected).strip()
                except Exception as e:
                    logger.error(f"LLM 生成摘要失败: {e}")

            # 如果 LLM 不可用或失败，使用简单截取作为回退
            if not summary_text:
                summary_text = conversation_text[:500]

            # 更新会话摘要
            await conn.execute(
                "UPDATE chat_sessions SET summary = $2 WHERE session_id = $1",
                session_id, summary_text,
            )

            # 删除已摘要的旧消息
            old_ids = [msg["id"] for msg in old_messages] if "id" in old_messages[0] else []
            if old_ids:
                placeholders = ",".join(f"${i+2}" for i in range(len(old_ids)))
                await conn.execute(
                    f"DELETE FROM chat_messages WHERE session_id = $1 AND id IN ({placeholders})",
                    session_id, *old_ids,
                )
            else:
                # 回退：按时间删除最早的 N 条
                await conn.execute(
                    """
                    DELETE FROM chat_messages
                    WHERE id IN (
                        SELECT id FROM chat_messages
                        WHERE session_id = $1
                        ORDER BY created_at
                        LIMIT $2
                    )
                    """,
                    session_id, HistoryService.SUMMARY_BATCH_SIZE,
                )

            # 更新消息计数
            await conn.execute(
                """
                UPDATE chat_sessions
                SET message_count = (
                    SELECT COUNT(*) FROM chat_messages WHERE session_id = $1
                )
                WHERE session_id = $1
                """,
                session_id,
            )

            logger.info(f"📝 会话 {session_id} 摘要已生成，清理了 {len(old_messages)} 条旧消息")
            return summary_text

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        粗略估算文本的 token 数
        中文约 1 字 ≈ 1.5 token，英文约 4 字符 ≈ 1 token
        """
        if not text:
            return 0
        chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_count = len(text) - chinese_count
        return int(chinese_count * 1.5 + other_count / 4)
