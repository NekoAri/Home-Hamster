"""
HomeHamster CRUD 服务层
封装所有数据库操作，供路由和 Agent 工具调用
"""

import asyncpg
import json
from datetime import datetime, date
from typing import Optional, Any


# ============================================================
# 账目 CRUD
# ============================================================

async def create_account(
    conn: asyncpg.Connection,
    amount: float,
    category: str,
    type: str = "expense",
    occurred_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> dict:
    """创建一条账目记录"""
    row = await conn.fetchrow(
        """
        INSERT INTO accounts (amount, category, type, occurred_at, note)
        VALUES ($1, $2, $3, COALESCE($4, NOW()), $5)
        RETURNING id, amount, category, type, occurred_at, note, created_at, updated_at
        """,
        amount, category, type, occurred_at, note,
    )
    return dict(row)


async def get_account(conn: asyncpg.Connection, account_id: int) -> Optional[dict]:
    """根据 ID 查询单条账目"""
    row = await conn.fetchrow(
        "SELECT id, amount, category, type, occurred_at, note, created_at, updated_at "
        "FROM accounts WHERE id = $1",
        account_id,
    )
    return dict(row) if row else None


async def list_accounts(
    conn: asyncpg.Connection,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> list[dict]:
    """查询账目列表，支持按分类、类型、时间范围筛选"""
    query = "SELECT id, amount, category, type, occurred_at, note, created_at, updated_at FROM accounts WHERE 1=1"
    params = []
    idx = 1

    if category:
        query += f" AND category = ${idx}"
        params.append(category)
        idx += 1
    if type:
        query += f" AND type = ${idx}"
        params.append(type)
        idx += 1
    if start_date:
        query += f" AND occurred_at >= ${idx}"
        params.append(start_date)
        idx += 1
    if end_date:
        query += f" AND occurred_at <= ${idx}"
        params.append(end_date)
        idx += 1

    query += f" ORDER BY occurred_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def update_account(
    conn: asyncpg.Connection,
    account_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新账目记录"""
    allowed_fields = {"amount", "category", "type", "occurred_at", "note"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_account(conn, account_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [account_id] + list(updates.values())
    query = (
        f"UPDATE accounts SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, amount, category, type, occurred_at, note, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_account(conn: asyncpg.Connection, account_id: int) -> bool:
    """删除账目记录"""
    result = await conn.execute("DELETE FROM accounts WHERE id = $1", account_id)
    return result.endswith("1")  # DELETE 1 表示成功删除一条


# ============================================================
# 物品类别 CRUD
# ============================================================

async def create_category(
    conn: asyncpg.Connection,
    name: str,
    code: str,
    description: Optional[str] = None,
) -> dict:
    """创建物品类别"""
    row = await conn.fetchrow(
        """
        INSERT INTO item_categories (name, code, description)
        VALUES ($1, $2, $3)
        RETURNING id, name, code, description, created_at, updated_at
        """,
        name, code, description,
    )
    return dict(row)


async def get_category(conn: asyncpg.Connection, category_id: int) -> Optional[dict]:
    """根据 ID 查询类别"""
    row = await conn.fetchrow(
        "SELECT id, name, code, description, created_at, updated_at "
        "FROM item_categories WHERE id = $1",
        category_id,
    )
    return dict(row) if row else None


async def list_categories(conn: asyncpg.Connection) -> list[dict]:
    """查询所有类别"""
    rows = await conn.fetch(
        "SELECT id, name, code, description, created_at, updated_at "
        "FROM item_categories ORDER BY id"
    )
    return [dict(row) for row in rows]


async def update_category(
    conn: asyncpg.Connection,
    category_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新类别"""
    allowed_fields = {"name", "code", "description"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_category(conn, category_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [category_id] + list(updates.values())
    query = (
        f"UPDATE item_categories SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, name, code, description, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_category(conn: asyncpg.Connection, category_id: int) -> bool:
    """删除类别"""
    result = await conn.execute("DELETE FROM item_categories WHERE id = $1", category_id)
    return result.endswith("1")


# ============================================================
# 物品仓储 CRUD
# ============================================================

async def create_inventory(
    conn: asyncpg.Connection,
    name: str,
    barcode: Optional[str] = None,
    category_id: Optional[int] = None,
    quantity: int = 0,
    unit: str = "个",
    location: Optional[str] = None,
    expiry_date: Optional[date] = None,
    custom_attrs: Optional[dict] = None,
) -> dict:
    """创建物品库存记录"""
    row = await conn.fetchrow(
        """
        INSERT INTO inventory (name, barcode, category_id, quantity, unit, location, expiry_date, custom_attrs)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        RETURNING id, name, barcode, category_id, quantity, unit, location, expiry_date, custom_attrs, created_at, updated_at
        """,
        name, barcode, category_id, quantity, unit, location, expiry_date,
        json.dumps(custom_attrs or {}, ensure_ascii=False),
    )
    return dict(row)


async def get_inventory(conn: asyncpg.Connection, inventory_id: int) -> Optional[dict]:
    """根据 ID 查询物品"""
    row = await conn.fetchrow(
        """
        SELECT i.id, i.name, i.barcode, i.category_id, c.name AS category_name,
               i.quantity, i.unit, i.location, i.expiry_date, i.custom_attrs,
               i.created_at, i.updated_at
        FROM inventory i
        LEFT JOIN item_categories c ON i.category_id = c.id
        WHERE i.id = $1
        """,
        inventory_id,
    )
    return dict(row) if row else None


async def list_inventory(
    conn: asyncpg.Connection,
    limit: int = 50,
    offset: int = 0,
    name: Optional[str] = None,
    category_id: Optional[int] = None,
    location: Optional[str] = None,
    barcode: Optional[str] = None,
) -> list[dict]:
    """查询物品列表，支持模糊搜索和筛选"""
    query = """
        SELECT i.id, i.name, i.barcode, i.category_id, c.name AS category_name,
               i.quantity, i.unit, i.location, i.expiry_date, i.custom_attrs,
               i.created_at, i.updated_at
        FROM inventory i
        LEFT JOIN item_categories c ON i.category_id = c.id
        WHERE 1=1
    """
    params = []
    idx = 1

    if name:
        query += f" AND i.name ILIKE ${idx}"
        params.append(f"%{name}%")
        idx += 1
    if category_id:
        query += f" AND i.category_id = ${idx}"
        params.append(category_id)
        idx += 1
    if location:
        query += f" AND i.location ILIKE ${idx}"
        params.append(f"%{location}%")
        idx += 1
    if barcode:
        query += f" AND i.barcode = ${idx}"
        params.append(barcode)
        idx += 1

    query += f" ORDER BY i.updated_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def update_inventory(
    conn: asyncpg.Connection,
    inventory_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新物品库存"""
    allowed_fields = {
        "name", "barcode", "category_id", "quantity", "unit",
        "location", "expiry_date", "custom_attrs",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_inventory(conn, inventory_id)

    # custom_attrs 需要转 JSON 字符串
    if "custom_attrs" in updates:
        updates["custom_attrs"] = json.dumps(updates["custom_attrs"], ensure_ascii=False)

    set_parts = []
    values = [inventory_id]
    for i, (k, v) in enumerate(updates.items()):
        if k == "custom_attrs":
            set_parts.append(f"{k} = ${i+2}::jsonb")
        else:
            set_parts.append(f"{k} = ${i+2}")
        values.append(v)

    set_clauses = ", ".join(set_parts)
    query = (
        f"UPDATE inventory SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, name, barcode, category_id, quantity, unit, location, expiry_date, custom_attrs, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_inventory(conn: asyncpg.Connection, inventory_id: int) -> bool:
    """删除物品库存记录"""
    result = await conn.execute("DELETE FROM inventory WHERE id = $1", inventory_id)
    return result.endswith("1")


# ============================================================
# Agent 记忆 CRUD
# ============================================================

async def save_memory(
    conn: asyncpg.Connection,
    user_id: str,
    memory_type: str,
    content: str,
    embedding: Optional[list[float]] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """保存 Agent 记忆（含向量嵌入）"""
    import numpy as np
    row = await conn.fetchrow(
        """
        INSERT INTO agent_memories (user_id, memory_type, content, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING id, user_id, memory_type, content, created_at, updated_at
        """,
        user_id, memory_type, content,
        np.array(embedding) if embedding else None,
        json.dumps(metadata or {}, ensure_ascii=False),
    )
    return dict(row)


async def search_memories(
    conn: asyncpg.Connection,
    user_id: str,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """基于向量相似度检索相关记忆"""
    import numpy as np
    rows = await conn.fetch(
        """
        SELECT id, memory_type, content, metadata, created_at,
               1 - (embedding <=> $2) AS similarity
        FROM agent_memories
        WHERE user_id = $1
        ORDER BY embedding <=> $2
        LIMIT $3
        """,
        user_id, np.array(query_embedding), limit,
    )
    return [dict(row) for row in rows]


# ============================================================
# LLM 配置 CRUD
# ============================================================

async def create_llm_config(
    conn: asyncpg.Connection,
    name: str,
    provider: str,
    api_key: str = "",
    base_url: Optional[str] = None,
    model_name: str = "",
    embedding_model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    is_active: bool = False,
) -> dict:
    """创建 LLM 配置"""
    # 如果设为激活，先取消其他激活配置
    if is_active:
        await conn.execute("UPDATE llm_configs SET is_active = FALSE WHERE is_active = TRUE")
    row = await conn.fetchrow(
        """
        INSERT INTO llm_configs (name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id, name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active, created_at, updated_at
        """,
        name, provider, api_key, base_url, model_name, embedding_model,
        temperature, max_tokens, is_active,
    )
    return dict(row)


async def get_llm_config(conn: asyncpg.Connection, config_id: int) -> Optional[dict]:
    """根据 ID 查询 LLM 配置"""
    row = await conn.fetchrow(
        "SELECT id, name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active, created_at, updated_at "
        "FROM llm_configs WHERE id = $1",
        config_id,
    )
    return dict(row) if row else None


async def get_active_llm_config(conn: asyncpg.Connection) -> Optional[dict]:
    """获取当前激活的 LLM 配置"""
    row = await conn.fetchrow(
        "SELECT id, name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active, created_at, updated_at "
        "FROM llm_configs WHERE is_active = TRUE LIMIT 1"
    )
    return dict(row) if row else None


async def list_llm_configs(conn: asyncpg.Connection) -> list[dict]:
    """查询所有 LLM 配置"""
    rows = await conn.fetch(
        "SELECT id, name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active, created_at, updated_at "
        "FROM llm_configs ORDER BY is_active DESC, id"
    )
    return [dict(row) for row in rows]


async def update_llm_config(
    conn: asyncpg.Connection,
    config_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新 LLM 配置"""
    allowed_fields = {
        "name", "provider", "api_key", "base_url", "model_name",
        "embedding_model", "temperature", "max_tokens", "is_active",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_llm_config(conn, config_id)

    # 如果设为激活，先取消其他激活配置
    if updates.get("is_active"):
        await conn.execute("UPDATE llm_configs SET is_active = FALSE WHERE is_active = TRUE AND id != $1", config_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [config_id] + list(updates.values())
    query = (
        f"UPDATE llm_configs SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, name, provider, api_key, base_url, model_name, embedding_model, temperature, max_tokens, is_active, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_llm_config(conn: asyncpg.Connection, config_id: int) -> bool:
    """删除 LLM 配置"""
    result = await conn.execute("DELETE FROM llm_configs WHERE id = $1", config_id)
    return result.endswith("1")


async def activate_llm_config(conn: asyncpg.Connection, config_id: int) -> Optional[dict]:
    """将指定 LLM 配置设为激活"""
    await conn.execute("UPDATE llm_configs SET is_active = FALSE WHERE is_active = TRUE")
    row = await conn.fetchrow(
        "UPDATE llm_configs SET is_active = TRUE WHERE id = $1 "
        "RETURNING id, name, provider, is_active",
        config_id,
    )
    return dict(row) if row else None


# ============================================================
# Agent 人设配置 CRUD
# ============================================================

async def create_agent_config(
    conn: asyncpg.Connection,
    name: str,
    avatar: str = "🐹",
    personality: str = "",
    system_prompt: Optional[str] = None,
    llm_config_id: Optional[int] = None,
    temperature: float = 0.7,
    is_active: bool = False,
) -> dict:
    """创建 Agent 人设配置"""
    if is_active:
        await conn.execute("UPDATE agent_configs SET is_active = FALSE WHERE is_active = TRUE")
    row = await conn.fetchrow(
        """
        INSERT INTO agent_configs (name, avatar, personality, system_prompt, llm_config_id, temperature, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, name, avatar, personality, system_prompt, llm_config_id, temperature, is_active, created_at, updated_at
        """,
        name, avatar, personality, system_prompt, llm_config_id, temperature, is_active,
    )
    return dict(row)


async def get_agent_config(conn: asyncpg.Connection, config_id: int) -> Optional[dict]:
    """根据 ID 查询 Agent 人设配置"""
    row = await conn.fetchrow(
        "SELECT id, name, avatar, personality, system_prompt, llm_config_id, temperature, is_active, created_at, updated_at "
        "FROM agent_configs WHERE id = $1",
        config_id,
    )
    return dict(row) if row else None


async def get_active_agent_config(conn: asyncpg.Connection) -> Optional[dict]:
    """获取当前激活的 Agent 人设配置"""
    row = await conn.fetchrow(
        "SELECT id, name, avatar, personality, system_prompt, llm_config_id, temperature, is_active, created_at, updated_at "
        "FROM agent_configs WHERE is_active = TRUE LIMIT 1"
    )
    return dict(row) if row else None


async def list_agent_configs(conn: asyncpg.Connection) -> list[dict]:
    """查询所有 Agent 人设配置"""
    rows = await conn.fetch(
        "SELECT id, name, avatar, personality, system_prompt, llm_config_id, temperature, is_active, created_at, updated_at "
        "FROM agent_configs ORDER BY is_active DESC, id"
    )
    return [dict(row) for row in rows]


async def update_agent_config(
    conn: asyncpg.Connection,
    config_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新 Agent 人设配置"""
    allowed_fields = {
        "name", "avatar", "personality", "system_prompt",
        "llm_config_id", "temperature", "is_active",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_agent_config(conn, config_id)

    if updates.get("is_active"):
        await conn.execute("UPDATE agent_configs SET is_active = FALSE WHERE is_active = TRUE AND id != $1", config_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [config_id] + list(updates.values())
    query = (
        f"UPDATE agent_configs SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, name, avatar, personality, system_prompt, llm_config_id, temperature, is_active, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_agent_config(conn: asyncpg.Connection, config_id: int) -> bool:
    """删除 Agent 人设配置"""
    result = await conn.execute("DELETE FROM agent_configs WHERE id = $1", config_id)
    return result.endswith("1")


async def activate_agent_config(conn: asyncpg.Connection, config_id: int) -> Optional[dict]:
    """将指定 Agent 人设配置设为激活"""
    await conn.execute("UPDATE agent_configs SET is_active = FALSE WHERE is_active = TRUE")
    row = await conn.fetchrow(
        "UPDATE agent_configs SET is_active = TRUE WHERE id = $1 "
        "RETURNING id, name, avatar, is_active",
        config_id,
    )
    return dict(row) if row else None
