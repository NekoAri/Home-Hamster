"""
HomeHamster CRUD 服务层
封装所有数据库操作，供路由和 Agent 工具调用
"""

import asyncpg
import json
from datetime import datetime, date
from typing import Optional, Any


# ============================================================
# 账本 CRUD
# ============================================================

async def create_ledger(
    conn: asyncpg.Connection,
    name: str,
    icon: str = "📔",
    color: str = "orange",
    description: Optional[str] = None,
    is_default: bool = False,
    sort_order: int = 0,
) -> dict:
    """创建账本"""
    # 如果设为默认，先取消其他默认账本
    if is_default:
        await conn.execute("UPDATE ledgers SET is_default = FALSE WHERE is_default = TRUE")
    row = await conn.fetchrow(
        """
        INSERT INTO ledgers (name, icon, color, description, is_default, sort_order)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, name, icon, color, description, is_default, sort_order, created_at, updated_at
        """,
        name, icon, color, description, is_default, sort_order,
    )
    return dict(row)


async def get_ledger(conn: asyncpg.Connection, ledger_id: int) -> Optional[dict]:
    """根据 ID 查询账本"""
    row = await conn.fetchrow(
        "SELECT id, name, icon, color, description, is_default, sort_order, created_at, updated_at "
        "FROM ledgers WHERE id = $1",
        ledger_id,
    )
    return dict(row) if row else None


async def get_ledger_by_name(conn: asyncpg.Connection, name: str) -> Optional[dict]:
    """根据名称查询账本（模糊匹配）"""
    row = await conn.fetchrow(
        "SELECT id, name, icon, color, description, is_default, sort_order, created_at, updated_at "
        "FROM ledgers WHERE name ILIKE $1 LIMIT 1",
        f"%{name}%",
    )
    return dict(row) if row else None


async def list_ledgers(
    conn: asyncpg.Connection,
    include_stats: bool = False,
) -> list[dict]:
    """查询所有账本，可选包含统计信息"""
    if not include_stats:
        rows = await conn.fetch(
            "SELECT id, name, icon, color, description, is_default, sort_order, created_at, updated_at "
            "FROM ledgers ORDER BY is_default DESC, sort_order ASC, id ASC"
        )
        return [dict(row) for row in rows]
    else:
        rows = await conn.fetch(
            """
            SELECT l.id, l.name, l.icon, l.color, l.description, l.is_default, l.sort_order,
                   l.created_at, l.updated_at,
                   COUNT(a.id) AS record_count,
                   COALESCE(SUM(CASE WHEN a.type = 'expense' THEN ABS(a.amount) ELSE 0 END), 0) AS total_expense,
                   COALESCE(SUM(CASE WHEN a.type = 'income' THEN a.amount ELSE 0 END), 0) AS total_income
            FROM ledgers l
            LEFT JOIN accounts a ON a.ledger_id = l.id
            GROUP BY l.id, l.name, l.icon, l.color, l.description, l.is_default, l.sort_order, l.created_at, l.updated_at
            ORDER BY l.is_default DESC, l.sort_order ASC, l.id ASC
            """
        )
        return [dict(row) for row in rows]


async def update_ledger(
    conn: asyncpg.Connection,
    ledger_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新账本"""
    allowed_fields = {"name", "icon", "color", "description", "is_default", "sort_order"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_ledger(conn, ledger_id)

    # 如果设为默认，先取消其他默认账本
    if updates.get("is_default"):
        await conn.execute("UPDATE ledgers SET is_default = FALSE WHERE is_default = TRUE AND id != $1", ledger_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [ledger_id] + list(updates.values())
    query = (
        f"UPDATE ledgers SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, name, icon, color, description, is_default, sort_order, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_ledger(conn: asyncpg.Connection, ledger_id: int) -> bool:
    """删除账本（不允许删除有记录的账本，或默认账本）"""
    # 检查是否为默认账本
    is_default = await conn.fetchval("SELECT is_default FROM ledgers WHERE id = $1", ledger_id)
    if is_default:
        return False
    # 检查是否有记录
    count = await conn.fetchval("SELECT COUNT(*) FROM accounts WHERE ledger_id = $1", ledger_id)
    if count > 0:
        return False
    result = await conn.execute("DELETE FROM ledgers WHERE id = $1", ledger_id)
    return result.endswith("1")


async def get_default_ledger_id(conn: asyncpg.Connection) -> int:
    """获取默认账本ID"""
    ledger_id = await conn.fetchval("SELECT id FROM ledgers WHERE is_default = TRUE ORDER BY id LIMIT 1")
    if not ledger_id:
        ledger_id = await conn.fetchval("SELECT id FROM ledgers ORDER BY id LIMIT 1")
    return ledger_id


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
    ledger_id: Optional[int] = None,
) -> dict:
    """创建一条账目记录"""
    # 如果未指定账本，使用默认账本
    if not ledger_id:
        ledger_id = await get_default_ledger_id(conn)
    row = await conn.fetchrow(
        """
        INSERT INTO accounts (amount, category, type, ledger_id, occurred_at, note)
        VALUES ($1, $2, $3, $4, COALESCE($5, NOW()), $6)
        RETURNING id, amount, category, type, ledger_id, occurred_at, note, created_at, updated_at
        """,
        amount, category, type, ledger_id, occurred_at, note,
    )
    return dict(row)


async def get_account(conn: asyncpg.Connection, account_id: int) -> Optional[dict]:
    """根据 ID 查询单条账目"""
    row = await conn.fetchrow(
        "SELECT a.id, a.amount, a.category, a.type, a.ledger_id, l.name AS ledger_name, "
        "a.occurred_at, a.note, a.created_at, a.updated_at "
        "FROM accounts a LEFT JOIN ledgers l ON a.ledger_id = l.id "
        "WHERE a.id = $1",
        account_id,
    )
    return dict(row) if row else None


async def list_accounts(
    conn: asyncpg.Connection,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    type: Optional[str] = None,
    ledger_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> list[dict]:
    """查询账目列表，支持按账本、分类、类型、时间范围筛选"""
    query = ("SELECT a.id, a.amount, a.category, a.type, a.ledger_id, l.name AS ledger_name, "
             "a.occurred_at, a.note, a.created_at, a.updated_at "
             "FROM accounts a LEFT JOIN ledgers l ON a.ledger_id = l.id WHERE 1=1")
    params = []
    idx = 1

    if ledger_id:
        query += f" AND a.ledger_id = ${idx}"
        params.append(ledger_id)
        idx += 1
    if category:
        query += f" AND a.category = ${idx}"
        params.append(category)
        idx += 1
    if type:
        query += f" AND a.type = ${idx}"
        params.append(type)
        idx += 1
    if start_date:
        query += f" AND a.occurred_at >= ${idx}"
        params.append(start_date)
        idx += 1
    if end_date:
        query += f" AND a.occurred_at <= ${idx}"
        params.append(end_date)
        idx += 1

    query += f" ORDER BY a.occurred_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def update_account(
    conn: asyncpg.Connection,
    account_id: int,
    **kwargs: Any,
) -> Optional[dict]:
    """更新账目记录"""
    allowed_fields = {"amount", "category", "type", "ledger_id", "occurred_at", "note"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
    if not updates:
        return await get_account(conn, account_id)

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [account_id] + list(updates.values())
    query = (
        f"UPDATE accounts SET {set_clauses} "
        f"WHERE id = $1 "
        f"RETURNING id, amount, category, type, ledger_id, occurred_at, note, created_at, updated_at"
    )
    row = await conn.fetchrow(query, *values)
    return dict(row) if row else None


async def delete_account(conn: asyncpg.Connection, account_id: int) -> bool:
    """删除账目记录"""
    result = await conn.execute("DELETE FROM accounts WHERE id = $1", account_id)
    return result.endswith("1")  # DELETE 1 表示成功删除一条


async def count_accounts(
    conn: asyncpg.Connection,
    category: Optional[str] = None,
    type: Optional[str] = None,
    ledger_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> int:
    """查询满足筛选条件的账目总数"""
    query = "SELECT COUNT(*) FROM accounts WHERE 1=1"
    params = []
    idx = 1
    if ledger_id:
        query += f" AND ledger_id = ${idx}"
        params.append(ledger_id)
        idx += 1
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
    return await conn.fetchval(query, *params)


async def get_accounts_summary(
    conn: asyncpg.Connection,
    ledger_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    查询指定时间范围（和账本）的账目统计摘要
    返回：总支出、总收入、净额、交易笔数、分类汇总
    """
    from datetime import datetime as dt

    now = dt.now()
    if not start_date:
        start_date = dt(now.year, now.month, 1)
    if not end_date:
        end_date = now

    # 构建条件
    conditions = ["occurred_at BETWEEN $1 AND $2"]
    params = [start_date, end_date]
    idx = 3
    if ledger_id:
        conditions.append(f"ledger_id = ${idx}")
        params.append(ledger_id)
        idx += 1
    where_clause = " AND ".join(conditions)

    # 总支出和总收入
    expense_row = await conn.fetchrow(
        f"SELECT COALESCE(SUM(ABS(amount)), 0) AS total, COUNT(*) AS cnt "
        f"FROM accounts WHERE type = 'expense' AND {where_clause}",
        *params,
    )
    income_row = await conn.fetchrow(
        f"SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
        f"FROM accounts WHERE type = 'income' AND {where_clause}",
        *params,
    )

    # 按分类汇总支出
    category_rows = await conn.fetch(
        f"""
        SELECT category, SUM(ABS(amount)) AS total, COUNT(*) AS count
        FROM accounts
        WHERE type = 'expense' AND {where_clause}
        GROUP BY category ORDER BY total DESC LIMIT 20
        """,
        *params,
    )

    # 按分类汇总收入
    income_category_rows = await conn.fetch(
        f"""
        SELECT category, SUM(amount) AS total, COUNT(*) AS count
        FROM accounts
        WHERE type = 'income' AND {where_clause}
        GROUP BY category ORDER BY total DESC LIMIT 20
        """,
        *params,
    )

    return {
        "total_expense": abs(float(expense_row["total"])),
        "expense_count": int(expense_row["cnt"]),
        "total_income": float(income_row["total"]),
        "income_count": int(income_row["cnt"]),
        "net_amount": float(income_row["total"]) - abs(float(expense_row["total"])),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "expense_by_category": [
            {"category": r["category"], "total": round(abs(float(r["total"])), 2), "count": int(r["count"])}
            for r in category_rows
        ],
        "income_by_category": [
            {"category": r["category"], "total": round(float(r["total"]), 2), "count": int(r["count"])}
            for r in income_category_rows
        ],
    }


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
        custom_attrs or {},  # codec 已注册 jsonb 编解码，直接传 dict
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


async def get_inventory_by_name(conn: asyncpg.Connection, name: str) -> Optional[dict]:
    """根据物品名称精确查询（用于采购时去重/累加库存）"""
    row = await conn.fetchrow(
        """
        SELECT i.id, i.name, i.barcode, i.category_id, c.name AS category_name,
               i.quantity, i.unit, i.location, i.expiry_date, i.custom_attrs,
               i.created_at, i.updated_at
        FROM inventory i
        LEFT JOIN item_categories c ON i.category_id = c.id
        WHERE i.name = $1
        LIMIT 1
        """,
        name,
    )
    return dict(row) if row else None


async def count_inventory(
    conn: asyncpg.Connection,
    name: Optional[str] = None,
    category_id: Optional[int] = None,
    location: Optional[str] = None,
    barcode: Optional[str] = None,
) -> int:
    """查询满足筛选条件的物品总数"""
    query = "SELECT COUNT(*) FROM inventory WHERE 1=1"
    params = []
    idx = 1

    if name:
        query += f" AND name ILIKE ${idx}"
        params.append(f"%{name}%")
        idx += 1
    if category_id:
        query += f" AND category_id = ${idx}"
        params.append(category_id)
        idx += 1
    if location:
        query += f" AND location ILIKE ${idx}"
        params.append(f"%{location}%")
        idx += 1
    if barcode:
        query += f" AND barcode = ${idx}"
        params.append(barcode)
        idx += 1

    return await conn.fetchval(query, *params)


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

    # custom_attrs 直接传 dict（连接池已注册 jsonb codec）
    if "custom_attrs" in updates:
        updates["custom_attrs"] = updates["custom_attrs"] or {}

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
        metadata or {},  # codec 已注册 jsonb 编解码，直接传 dict
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


# ============================================================
# Agent 模型绑定（主从架构：主 Agent 与各子 Agent 可使用不同模型）
# ============================================================

async def list_agent_model_bindings(conn: asyncpg.Connection) -> dict[str, int]:
    """
    读取所有 Agent 模型绑定。

    Returns:
        {agent_key: llm_config_id}，如 {"master": 1, "bookkeeping": 2}
    """
    rows = await conn.fetch("SELECT agent_key, llm_config_id FROM agent_model_bindings")
    return {row["agent_key"]: row["llm_config_id"] for row in rows}


async def set_agent_model_binding(
    conn: asyncpg.Connection,
    agent_key: str,
    llm_config_id: Optional[int],
) -> None:
    """
    设置/清除某个 Agent 的模型绑定。

    - llm_config_id 不为空：upsert 绑定
    - llm_config_id 为空：删除绑定（回退到主 Agent 的模型）
    """
    if llm_config_id is None:
        await conn.execute("DELETE FROM agent_model_bindings WHERE agent_key = $1", agent_key)
        return

    await conn.execute(
        """
        INSERT INTO agent_model_bindings (agent_key, llm_config_id)
        VALUES ($1, $2)
        ON CONFLICT (agent_key) DO UPDATE
        SET llm_config_id = EXCLUDED.llm_config_id, updated_at = NOW()
        """,
        agent_key, llm_config_id,
    )


async def ensure_agent_model_bindings_table(conn: asyncpg.Connection) -> None:
    """确保绑定表存在（对已有部署自动补建，无需手工跑迁移 SQL）"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_model_bindings (
            agent_key     VARCHAR(50) PRIMARY KEY,
            llm_config_id BIGINT      NOT NULL,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_agent_model_bindings_llm
                FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)
                ON DELETE CASCADE
        )
        """
    )


# ============================================================
# 通用事件表（events）—— 早报 / 提醒闭环 / 日程待办的统一落点
# ============================================================

async def ensure_events_table(conn: asyncpg.Connection) -> None:
    """确保 events 表存在（对已有部署自动补建，无需手工跑迁移 SQL）"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id          BIGSERIAL PRIMARY KEY,
            kind        VARCHAR(30)   NOT NULL,
            title       VARCHAR(200)  NOT NULL,
            detail      TEXT,
            due_at      TIMESTAMPTZ,
            remind_at   TIMESTAMPTZ,
            repeat_rule VARCHAR(100),
            status      VARCHAR(20)   NOT NULL DEFAULT 'pending',
            ref_type    VARCHAR(50),
            ref_id      BIGINT,
            owner_id    VARCHAR(100)  NOT NULL DEFAULT 'default',
            payload     JSONB         NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_remind_at ON events (remind_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_status_remind_at ON events (status, remind_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_ref ON events (ref_type, ref_id)"
    )


# ============================================================
# 通知渠道表（notify_channels）
# ============================================================

async def ensure_notify_channels_table(conn: asyncpg.Connection) -> None:
    """确保 notify_channels 表存在（对已有部署自动补建）"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notify_channels (
            id          BIGSERIAL PRIMARY KEY,
            type        VARCHAR(30)   NOT NULL UNIQUE,
            name        VARCHAR(100)  NOT NULL DEFAULT '',
            config      JSONB         NOT NULL DEFAULT '{}',
            enabled     BOOLEAN       NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )


async def list_notify_channels(conn: asyncpg.Connection) -> list[dict]:
    """查询所有通知渠道配置（含 api key 明文，仅后端使用；对外展示需自行脱敏）"""
    rows = await conn.fetch(
        "SELECT id, type, name, config, enabled, created_at, updated_at "
        "FROM notify_channels ORDER BY id"
    )
    return [dict(r) for r in rows]


async def upsert_notify_channel(
    conn: asyncpg.Connection,
    type_: str,
    name: str,
    config: dict,
    enabled: bool,
) -> dict:
    """
    保存通知渠道配置：同 type 只保留一条（单渠道自用场景）。
    已存在同 type 渠道则覆盖更新，否则新建。
    """
    row = await conn.fetchrow(
        """
        INSERT INTO notify_channels (type, name, config, enabled)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (type) DO UPDATE
        SET name = EXCLUDED.name, config = EXCLUDED.config,
            enabled = EXCLUDED.enabled, updated_at = NOW()
        RETURNING id, type, name, config, enabled, created_at, updated_at
        """,
        type_, name, config or {}, enabled,
    )
    return dict(row) if row else {}


async def get_enabled_notify_channel(conn: asyncpg.Connection) -> Optional[dict]:
    """取当前启用的通知渠道（最多一个），没有则返回 None"""
    row = await conn.fetchrow(
        "SELECT id, type, name, config, enabled "
        "FROM notify_channels WHERE enabled = TRUE ORDER BY id LIMIT 1"
    )
    return dict(row) if row else {}


# ============================================================
# 成员维度（owner_id）：老库自动补列
# ============================================================

_OWNER_TABLES = ("accounts", "inventory", "chat_sessions")


async def ensure_owner_id_columns(conn: asyncpg.Connection) -> None:
    """为 accounts / inventory / chat_sessions 自动补 owner_id 列（默认 'default'）"""
    for table in _OWNER_TABLES:
        await conn.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN IF NOT EXISTS owner_id VARCHAR(100) NOT NULL DEFAULT 'default'"
        )


async def ensure_all_tables(conn: asyncpg.Connection) -> None:
    """
    应用启动时的自动补建入口：对老库补齐所有新增表和列。
    新增的 ensure_xxx_table 应在此注册；agent_model_bindings
    由 AgentManager 加载时自行补建，此处不重复。
    """
    await ensure_events_table(conn)
    await ensure_notify_channels_table(conn)
    await ensure_daily_reports_table(conn)
    await ensure_app_settings_table(conn)
    await ensure_owner_id_columns(conn)
    await ensure_memory_embedding_dim(conn)


async def ensure_memory_embedding_dim(conn: asyncpg.Connection, dim: int = 768) -> None:
    """
    确保 agent_memories.embedding 的向量维度与当前嵌入模型一致（默认 768，
    对应本地 nomic-embed-text-v1.5）。老库若为 1536（OpenAI 维度）自动迁移。
    表为空才迁移，避免破坏已有向量数据。
    """
    row = await conn.fetchrow(
        "SELECT a.atttypmod FROM pg_attribute a "
        "WHERE a.attrelid = 'agent_memories'::regclass AND a.attname = 'embedding'"
    )
    if row is None:
        return  # 表不存在（首次部署由 init.sql / AgentManager 建表）
    if row["atttypmod"] == dim:
        return
    count = await conn.fetchval("SELECT count(*) FROM agent_memories")
    if count:
        # 已有数据不做静默迁移，提示人工处理
        import logging
        logging.getLogger(__name__).warning(
            f"agent_memories.embedding 维度({row['atttypmod']})与期望({dim})不一致"
            f"且表内有 {count} 条数据，跳过自动迁移，请人工处理"
        )
        return
    await conn.execute("DROP INDEX IF EXISTS idx_agent_memories_embedding_hnsw")
    await conn.execute(f"ALTER TABLE agent_memories ALTER COLUMN embedding TYPE vector({dim})")
    await conn.execute(
        "CREATE INDEX idx_agent_memories_embedding_hnsw "
        "ON agent_memories USING hnsw (embedding vector_cosine_ops)"
    )


# ============================================================
# 每日早报表（daily_reports）—— 幂等去重 + 历史早报统一数据源
# ============================================================

async def ensure_daily_reports_table(conn: asyncpg.Connection) -> None:
    """确保 daily_reports 表存在（对已有部署自动补建）"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_reports (
            id            BIGSERIAL PRIMARY KEY,
            report_date   DATE          NOT NULL UNIQUE,
            template_text TEXT          NOT NULL,
            polished_text TEXT,
            is_polished   BOOLEAN       NOT NULL DEFAULT FALSE,
            status        VARCHAR(20)   NOT NULL DEFAULT 'pending',
            fail_reason   TEXT,
            trigger_type  VARCHAR(20)   NOT NULL DEFAULT 'scheduled',
            data          JSONB         NOT NULL DEFAULT '{}',
            sent_at       TIMESTAMPTZ,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )


async def upsert_daily_report(
    conn: asyncpg.Connection,
    report_date: date,
    template_text: str,
    polished_text: Optional[str],
    is_polished: bool,
    status: str,
    trigger_type: str,
    data: dict,
    fail_reason: Optional[str] = None,
    sent_at: Optional[datetime] = None,
) -> dict:
    """
    写入/更新当日早报记录（report_date 唯一，同日重复触发覆盖旧记录）。
    """
    row = await conn.fetchrow(
        """
        INSERT INTO daily_reports
            (report_date, template_text, polished_text, is_polished,
             status, trigger_type, data, fail_reason, sent_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (report_date) DO UPDATE
        SET template_text = EXCLUDED.template_text,
            polished_text = EXCLUDED.polished_text,
            is_polished = EXCLUDED.is_polished,
            status = EXCLUDED.status,
            trigger_type = EXCLUDED.trigger_type,
            data = EXCLUDED.data,
            fail_reason = EXCLUDED.fail_reason,
            sent_at = EXCLUDED.sent_at,
            updated_at = NOW()
        RETURNING *
        """,
        report_date, template_text, polished_text, is_polished,
        status, trigger_type, data or {},
        fail_reason, sent_at,
    )
    return dict(row) if row else {}


async def get_daily_report(conn: asyncpg.Connection, report_date: date) -> Optional[dict]:
    """取某一天的早报记录"""
    row = await conn.fetchrow("SELECT * FROM daily_reports WHERE report_date = $1", report_date)
    return dict(row) if row else {}


async def list_daily_reports(conn: asyncpg.Connection, limit: int = 30) -> list[dict]:
    """按日期倒序列出历史早报（前端「今日简报」历史列表用）"""
    rows = await conn.fetch(
        "SELECT * FROM daily_reports ORDER BY report_date DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]


# ============================================================
# 应用设置表（app_settings）—— 简单 KV
# ============================================================

async def ensure_app_settings_table(conn: asyncpg.Connection) -> None:
    """确保 app_settings 表存在（对已有部署自动补建）"""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key        VARCHAR(100) PRIMARY KEY,
            value      JSONB         NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )


async def get_app_setting(conn: asyncpg.Connection, key: str) -> Optional[dict]:
    """读取一个设置项（返回 JSONB 内容，不存在返回 None）"""
    row = await conn.fetchrow("SELECT value FROM app_settings WHERE key = $1", key)
    return dict(row["value"]) if row else None


async def set_app_setting(conn: asyncpg.Connection, key: str, value: dict) -> None:
    """写入一个设置项（upsert）"""
    await conn.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW()
        """,
        key, value or {},
    )


# ============================================================
# 事件 CRUD（P2 提醒闭环）
# ============================================================

async def get_event_by_ref(
    conn: asyncpg.Connection,
    kind: str,
    ref_type: str,
    ref_id: int,
) -> Optional[dict]:
    """按 (kind, ref_type, ref_id) 查事件（同一对象同一类事件只留一条）"""
    row = await conn.fetchrow(
        "SELECT * FROM events WHERE kind = $1 AND ref_type = $2 AND ref_id = $3 "
        "ORDER BY id DESC LIMIT 1",
        kind, ref_type, ref_id,
    )
    return dict(row) if row else {}


async def create_event(
    conn: asyncpg.Connection,
    kind: str,
    title: str,
    detail: str = "",
    due_at: Optional[datetime] = None,
    remind_at: Optional[datetime] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> dict:
    """创建事件"""
    row = await conn.fetchrow(
        """
        INSERT INTO events (kind, title, detail, due_at, remind_at,
                            ref_type, ref_id, payload)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        kind, title, detail, due_at, remind_at,
        ref_type, ref_id, payload or {},
    )
    return dict(row)


async def update_event_fields(
    conn: asyncpg.Connection,
    event_id: int,
    title: Optional[str] = None,
    detail: Optional[str] = None,
    due_at=...,   # type: ignore  # 用哨兵区分"不更新"与"置空"
    remind_at=...,  # type: ignore
    payload: Optional[dict] = None,
) -> None:
    """按需更新事件字段（None 语义与"不更新"用哨兵区分）"""
    sets, params = [], []
    if title is not None:
        params.append(title); sets.append(f"title = ${len(params)}")
    if detail is not None:
        params.append(detail); sets.append(f"detail = ${len(params)}")
    if due_at is not ...:
        params.append(due_at); sets.append(f"due_at = ${len(params)}")
    if remind_at is not ...:
        params.append(remind_at); sets.append(f"remind_at = ${len(params)}")
    if payload is not None:
        params.append(payload)
        sets.append(f"payload = ${len(params)}")
    if not sets:
        return
    params.append(event_id)
    await conn.execute(
        f"UPDATE events SET {', '.join(sets)} WHERE id = ${len(params)}", *params,
    )


async def set_event_status(
    conn: asyncpg.Connection,
    event_id: int,
    status: str,
) -> Optional[dict]:
    """更新事件状态（done / snoozed / dismissed / pending），返回更新后的记录"""
    row = await conn.fetchrow(
        "UPDATE events SET status = $2 WHERE id = $1 RETURNING *",
        event_id, status,
    )
    return dict(row) if row else {}


async def get_event(conn: asyncpg.Connection, event_id: int) -> Optional[dict]:
    row = await conn.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    return dict(row) if row else {}


async def list_events(
    conn: asyncpg.Connection,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """按提醒时间正序列出事件（前端待处理列表用）"""
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if status:
        params.append(status)
        query += f" AND status = ${len(params)}"
    if kind:
        params.append(kind)
        query += f" AND kind = ${len(params)}"
    query += f" ORDER BY COALESCE(remind_at, due_at, created_at) ASC LIMIT ${len(params) + 1 if params else 1}"
    params.append(limit)
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


async def get_due_reminders(conn: asyncpg.Connection, now: datetime, limit: int = 20) -> list[dict]:
    """取到点该提醒的事件（pending / snoozed 且 remind_at <= now）"""
    rows = await conn.fetch(
        """
        SELECT * FROM events
        WHERE status IN ('pending', 'snoozed')
          AND remind_at IS NOT NULL AND remind_at <= $1
        ORDER BY remind_at ASC LIMIT $2
        """,
        now, limit,
    )
    return [dict(r) for r in rows]


# ---- 记忆系统（P3） ----

async def get_memory_by_content(
    conn: asyncpg.Connection,
    user_id: str,
    content: str,
) -> Optional[dict]:
    """按内容精确查记忆（抽取去重用）"""
    row = await conn.fetchrow(
        "SELECT * FROM agent_memories WHERE user_id = $1 AND content = $2 LIMIT 1",
        user_id, content,
    )
    return dict(row) if row else {}


async def create_memory(
    conn: asyncpg.Connection,
    user_id: str,
    memory_type: str,
    content: str,
    embedding: Optional[list[float]] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """写入一条记忆（embedding 可为 None，仅支持精确匹配检索）"""
    row = await conn.fetchrow(
        """
        INSERT INTO agent_memories (user_id, memory_type, content, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id, memory_type, content, embedding,
        metadata or {},
    )
    return dict(row)


async def list_memories(
    conn: asyncpg.Connection,
    user_id: str,
    memory_type: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """列出记忆（不含向量，前端列表页用）"""
    query = ("SELECT id, user_id, memory_type, content, metadata, created_at, updated_at "
             "FROM agent_memories WHERE user_id = $1")
    params: list = [user_id]
    if memory_type:
        params.append(memory_type)
        query += f" AND memory_type = ${len(params)}"
    query += f" ORDER BY updated_at DESC LIMIT ${len(params) + 1}"
    params.append(limit)
    rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


async def update_memory_content(
    conn: asyncpg.Connection,
    memory_id: int,
    content: str,
) -> Optional[dict]:
    """纠正记忆内容（纠正后向量失效，置空以避免过期语义）"""
    row = await conn.fetchrow(
        "UPDATE agent_memories SET content = $2, embedding = NULL WHERE id = $1 RETURNING *",
        memory_id, content,
    )
    return dict(row) if row else {}


async def delete_memory(conn: asyncpg.Connection, memory_id: int) -> bool:
    result = await conn.execute("DELETE FROM agent_memories WHERE id = $1", memory_id)
    return result.endswith("1")


async def search_similar_memories(
    conn: asyncpg.Connection,
    user_id: str,
    embedding: list[float],
    limit: int = 5,
    min_similarity: float = 0.75,
    memory_types: tuple[str, ...] = ("preference", "fact", "habit"),
) -> list[dict]:
    """向量近邻检索记忆（余弦相似度阈值过滤）"""
    rows = await conn.fetch(
        """
        SELECT id, user_id, memory_type, content, metadata,
               1 - (embedding <=> $2::vector) AS similarity
        FROM agent_memories
        WHERE user_id = $1
          AND memory_type = ANY($3)
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> $2::vector) >= $4
        ORDER BY embedding <=> $2::vector
        LIMIT $5
        """,
        user_id, embedding, list(memory_types), min_similarity, limit,
    )
    return [dict(r) for r in rows]


async def search_exact_memories(
    conn: asyncpg.Connection,
    user_id: str,
    keyword: str,
    limit: int = 5,
    memory_types: tuple[str, ...] = ("preference", "fact", "habit"),
) -> list[dict]:
    """SQL 精确/包含匹配检索（记忆内容出现在用户消息中，视为直接相关）"""
    rows = await conn.fetch(
        """
        SELECT id, user_id, memory_type, content, metadata
        FROM agent_memories
        WHERE user_id = $1
          AND memory_type = ANY($2)
          AND length(content) >= 2
          AND position(content in $3) > 0
        ORDER BY updated_at DESC
        LIMIT $4
        """,
        user_id, list(memory_types), keyword, limit,
    )
    return [dict(r) for r in rows]
