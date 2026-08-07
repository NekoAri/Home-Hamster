"""
统计概览路由
提供仪表盘所需的数据汇总：账目统计、库存统计、预警信息
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, date, timedelta
from app.services import crud
from app.database import get_pool

router = APIRouter(prefix="/api/summary", tags=["统计概览"])


@router.get("/overview", summary="获取总览数据")
async def get_overview(
    start_date: Optional[datetime] = Query(None, description="开始时间（默认本月1号）"),
    end_date: Optional[datetime] = Query(None, description="结束时间（默认当前）"),
    ledger_id: Optional[int] = Query(None, description="按账本筛选（不传则查全部账本）"),
):
    """获取仪表盘总览数据：总收入、总支出、净额、交易笔数、分类汇总，可按账本筛选"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 默认查询本月数据
        now = datetime.now()
        if not start_date:
            start_date = datetime(now.year, now.month, 1)
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
            f"SELECT COALESCE(SUM(amount), 0) AS total FROM accounts "
            f"WHERE type = 'expense' AND {where_clause}",
            *params,
        )
        income_row = await conn.fetchrow(
            f"SELECT COALESCE(SUM(amount), 0) AS total FROM accounts "
            f"WHERE type = 'income' AND {where_clause}",
            *params,
        )

        # 交易笔数
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) AS cnt FROM accounts WHERE {where_clause}",
            *params,
        )

        # 按分类汇总支出
        category_rows = await conn.fetch(
            f"""
            SELECT category, SUM(ABS(amount)) AS total, COUNT(*) AS count
            FROM accounts
            WHERE type = 'expense' AND {where_clause}
            GROUP BY category ORDER BY total DESC LIMIT 10
            """,
            *params,
        )

        # 近7天每日支出趋势
        daily_rows = await conn.fetch(
            """
            SELECT DATE(occurred_at) AS day, SUM(ABS(amount)) AS expense, COUNT(*) AS cnt
            FROM accounts
            WHERE type = 'expense'
              AND occurred_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(occurred_at)
            ORDER BY day
            """
        )

        total_expense = abs(float(expense_row["total"]))
        total_income = float(income_row["total"])
        net = total_income - total_expense

        return {
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "net_amount": round(net, 2),
            "transaction_count": int(count_row["cnt"]),
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "category_breakdown": [
                {"category": r["category"], "total": round(abs(float(r["total"])), 2), "count": int(r["count"])}
                for r in category_rows
            ],
            "daily_trend": [
                {"date": r["day"].isoformat() if r["day"] else "", "expense": round(abs(float(r["expense"])), 2), "count": int(r["cnt"])}
                for r in daily_rows
            ],
        }


@router.get("/inventory-stats", summary="获取库存统计")
async def get_inventory_stats():
    """获取库存相关统计：总物品数、低库存预警、临期预警"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 库存总览
        total_row = await conn.fetchrow(
            "SELECT COUNT(*) AS items, COALESCE(SUM(quantity), 0) AS total_qty "
            "FROM inventory"
        )

        # 低库存预警（数量 <= 5）
        low_stock = await conn.fetch(
            """
            SELECT id, name, quantity, unit, location, category_id
            FROM inventory WHERE quantity <= 5
            ORDER BY quantity ASC
            """
        )

        # 临期预警（30天内过期）
        today = date.today()
        expiry_threshold = today + timedelta(days=30)
        expiring = await conn.fetch(
            """
            SELECT id, name, quantity, unit, location, expiry_date, category_id
            FROM inventory
            WHERE expiry_date IS NOT NULL AND expiry_date <= $1
            ORDER BY expiry_date ASC
            """,
            expiry_threshold,
        )

        # 已过期
        expired = await conn.fetch(
            """
            SELECT id, name, quantity, unit, location, expiry_date
            FROM inventory
            WHERE expiry_date IS NOT NULL AND expiry_date < $1
            ORDER BY expiry_date ASC
            """,
            today,
        )

        # 按位置统计库存
        location_rows = await conn.fetch(
            """
            SELECT COALESCE(location, '未分类') AS location,
                   COUNT(*) AS items, SUM(quantity) AS total_qty
            FROM inventory GROUP BY location ORDER BY total_qty DESC
            """
        )

        # 按类别统计
        category_stats = await conn.fetch(
            """
            SELECT COALESCE(c.name, '未分类') AS category_name,
                   COUNT(i.id) AS items, COALESCE(SUM(i.quantity), 0) AS total_qty
            FROM inventory i
            LEFT JOIN item_categories c ON i.category_id = c.id
            GROUP BY c.name ORDER BY total_qty DESC
            """
        )

        return {
            "total_items": int(total_row["items"]),
            "total_quantity": int(total_row["total_qty"]),
            "low_stock_alerts": [dict(r) for r in low_stock],
            "expiring_alerts": [dict(r) for r in expiring],
            "expired_items": [dict(r) for r in expired],
            "location_breakdown": [
                {"location": r["location"], "items": int(r["items"]), "total_quantity": int(r["total_qty"])}
                for r in location_rows
            ],
            "category_breakdown": [
                {"category": r["category_name"], "items": int(r["items"]), "total_quantity": int(r["total_qty"])}
                for r in category_stats
            ],
        }


@router.get("/accounts/count", summary="查询账目总数（用于分页）")
async def count_accounts(
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    ledger_id: Optional[int] = Query(None, description="按账本筛选"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    """查询满足筛选条件的账目总数，供前端分页计算"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT COUNT(*) AS total FROM accounts WHERE 1=1"
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

        row = await conn.fetchrow(query, *params)
        return {"total": int(row["total"])}


@router.get("/inventory/count", summary="查询物品总数（用于分页）")
async def count_inventory(
    name: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    barcode: Optional[str] = Query(None),
):
    """查询满足筛选条件的物品总数，供前端分页计算"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT COUNT(*) AS total FROM inventory WHERE 1=1"
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

        row = await conn.fetchrow(query, *params)
        return {"total": int(row["total"])}
