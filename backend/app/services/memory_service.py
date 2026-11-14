"""
记忆系统服务（P3）

设计约定：
- 抽取：一轮对话结束后，用 LLM 从「用户消息 + 助手回复」抽取结构化事实
  （memory_type: preference / fact / habit），confidence < 0.7 不入库。
  后台异步执行，失败静默，绝不影响对话本身。
- 检索：preference/fact 优先 SQL 精确匹配（记忆内容出现在用户消息中），
  再走向量 top-k（余弦相似度 >= 0.75 阈值过滤），去重后按相关度排序。
- 注入：命中记忆拼成独立段落追加到主 Agent 系统提示词，最多 8 条，控制 token。
- 可见：所有记忆可在前端列表页查看/删除/纠正——记忆不可见 = 不可信。
"""

import asyncio
import json
import logging
from typing import Optional

from app.database import get_pool
from app.services import crud
from app.services.llm_provider import embed_texts

logger = logging.getLogger(__name__)

USER_ID = "default"  # 单用户约定（与全项目一致）

VALID_MEMORY_TYPES = ("preference", "fact", "habit")
MIN_CONFIDENCE = 0.7          # 低置信度不入库
SIMILARITY_THRESHOLD = 0.75   # 向量检索阈值
MAX_INJECT = 8                # 注入提示词的最大条数（控制 token）

EXTRACT_SYSTEM_PROMPT = """你负责从家庭管家的对话中抽取值得长期记住的「结构化事实」。

只抽取以下三类：
- preference：主人的偏好（如"牛奶要买全脂的"、"记账分类喜欢用'买菜'"）
- fact：稳定的事实（如"家里有两口人"、"冰箱是双开门的"）
- habit：重复的习惯（如"每周日采购一次"、"每天早上喝一杯咖啡"）

不要抽取：一次性的临时信息（如"今天买了牛奶"）、账目数字、库存数量、闲聊。
每条记忆必须是一句独立、具体、可长期成立的中文陈述。

只输出 JSON 数组（不要输出其他任何文字）：
[{"memory_type": "preference|fact|habit", "content": "...", "confidence": 0.0~1.0}]

如果对话里没有值得记住的内容，输出 []。"""


# ============================================================
# 抽取与入库
# ============================================================

def _parse_extract_reply(text: str) -> list[dict]:
    """解析 LLM 返回的 JSON（容忍 ```json 围栏）"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


async def extract_and_store(session_id: str, user_content: str, assistant_content: str) -> int:
    """
    抽取并存储本轮对话的记忆。返回入库条数。
    任何失败只记日志，返回 0，不影响主流程。
    """
    # 太短的对话不值得抽取
    if len(user_content.strip()) < 6:
        return 0

    try:
        from app.services.agent_manager import AgentManager

        manager = AgentManager.get_instance()
        provider = await manager.get_provider()
        llm_config = manager.get_llm_config()
        if provider is None or llm_config is None:
            logger.info("记忆抽取跳过：LLM 不可用")
            return 0

        async def _collect_reply() -> str:
            chunks = []
            async for chunk in provider.chat_stream(
                [
                    {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"【用户】{user_content}\n【管家】{assistant_content}",
                    },
                ],
                # 结构化抽取是工具型调用，关闭推理模型思考链，避免超时
                extra_body={"reasoning_effort": "none"},
            ):
                if chunk:
                    chunks.append(chunk)
            return "".join(chunks)

        # 本地推理模型思考较慢，给足 120s 超时；超时按失败处理
        reply = await asyncio.wait_for(_collect_reply(), timeout=120)
        if not reply.strip():
            logger.info("记忆抽取跳过：LLM 返回为空（推理模型可能只输出了思考链）")
            return 0

        items = _parse_extract_reply(reply)
        if not items:
            logger.info(f"记忆抽取跳过：未解析出结构化记忆，原始返回前 200 字: {reply[:200]}")
            return 0
    except asyncio.TimeoutError:
        logger.warning("记忆抽取超时（120s），跳过本轮")
        return 0
    except Exception as e:
        logger.warning(f"记忆抽取失败（跳过本轮）: {e}")
        return 0

    stored = 0
    try:
        # 批量生成向量（embedding_model 未配置时为 None，仅走精确匹配检索）
        contents = [
            str(i.get("content", "")).strip()
            for i in items
            if str(i.get("content", "")).strip()
        ]
        embeddings: list[Optional[list[float]]] = [None] * len(contents)
        if contents:
            try:
                vectors = await embed_texts(contents, llm_config)
                if vectors and len(vectors) == len(contents):
                    embeddings = vectors
            except Exception as e:
                logger.warning(f"生成记忆向量失败（降级为仅精确匹配）: {e}")

        pool = await get_pool()
        async with pool.acquire() as conn:
            for item, content, emb in zip(items, contents, embeddings):
                memory_type = str(item.get("memory_type", "")).strip()
                if memory_type not in VALID_MEMORY_TYPES:
                    continue
                try:
                    confidence = float(item.get("confidence", 0))
                except (TypeError, ValueError):
                    continue
                if confidence < MIN_CONFIDENCE:
                    continue
                # 同内容去重（已存在则跳过）
                if await crud.get_memory_by_content(conn, USER_ID, content):
                    continue
                # 向量级语义去重：换说法的重复记忆也不入库（相似度 >= 0.9 视为同一事实）
                if emb is not None:
                    similar = await crud.search_similar_memories(
                        conn, USER_ID, emb, limit=1, min_similarity=0.9,
                    )
                    if similar:
                        logger.info(f"记忆语义重复，跳过: {content} ≈ {similar[0]['content']}")
                        continue
                await crud.create_memory(
                    conn, USER_ID, memory_type, content,
                    embedding=emb,
                    metadata={"confidence": confidence, "session_id": session_id},
                )
                stored += 1
    except Exception as e:
        logger.warning(f"记忆入库失败: {e}")
        return 0

    if stored:
        logger.info(f"🧠 本轮对话沉淀 {stored} 条记忆")
    return stored


def spawn_extraction(session_id: str, user_content: str, assistant_content: str) -> None:
    """后台异步抽取（fire-and-forget，不阻塞对话流）"""
    try:
        asyncio.get_running_loop().create_task(
            extract_and_store(session_id, user_content, assistant_content)
        )
    except RuntimeError:
        pass


# ============================================================
# 检索与注入
# ============================================================

async def retrieve_relevant(user_message: str, limit: int = MAX_INJECT) -> list[dict]:
    """
    检索与用户消息相关的记忆：
    1. SQL 精确匹配优先（记忆内容出现在用户消息中）
    2. 向量 top-k（余弦相似度 >= 0.75），embedding 不可用时跳过
    去重合并，精确匹配排前。
    """
    results: list[dict] = []
    seen_ids: set[int] = set()

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1) 精确匹配
            exact = await crud.search_exact_memories(conn, USER_ID, user_message)
            for m in exact:
                if m["id"] not in seen_ids:
                    m["_exact"] = True
                    seen_ids.add(m["id"])
                    results.append(m)

            # 2) 向量检索
            try:
                from app.services.agent_manager import AgentManager

                llm_config = AgentManager.get_instance().get_llm_config()
                if llm_config is not None:
                    vector = await embed_texts([user_message], llm_config)
                    if vector and vector[0]:
                        similar = await crud.search_similar_memories(
                            conn, USER_ID, vector[0],
                            limit=limit, min_similarity=SIMILARITY_THRESHOLD,
                        )
                        for m in similar:
                            if m["id"] not in seen_ids:
                                m["_similarity"] = float(m.pop("similarity", 0))
                                seen_ids.add(m["id"])
                                results.append(m)
            except Exception as e:
                logger.warning(f"记忆向量检索失败（仅用精确匹配）: {e}")
    except Exception as e:
        logger.error(f"记忆检索失败: {e}")
        return []

    # 精确匹配在前，其余按相似度排序，截断条数控制 token
    exact_first = [m for m in results if m.get("_exact")]
    rest = [m for m in results if not m.get("_exact")]
    rest.sort(key=lambda m: m.get("_similarity", 0), reverse=True)
    return (exact_first + rest)[:limit]


async def build_prompt_section(user_message: str) -> str:
    """把命中记忆拼成注入主 Agent 提示词的独立段落（无命中返回空串）"""
    try:
        memories = await retrieve_relevant(user_message)
    except Exception as e:
        logger.warning(f"记忆注入失败（跳过）: {e}")
        return ""
    if not memories:
        return ""

    type_labels = {"preference": "偏好", "fact": "事实", "habit": "习惯"}
    lines = [
        "",
        "## 关于主人的记忆（长期记忆，回答时可自然运用，不要生硬复述）",
    ]
    for m in memories:
        label = type_labels.get(m["memory_type"], "记忆")
        lines.append(f"- [{label}] {m['content']}")
    lines.append("")
    return "\n".join(lines)
