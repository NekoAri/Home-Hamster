"""
事件服务（P2 提醒闭环）

职责：
1. sync_inventory_events：把库存的临期/过期/低库存同步成 events（同一对象同一类事件只留一条，
   用户已 done/dismissed 的不再重建，避免噪音）。
2. scan_due_reminders：定时扫描到点事件 → 推送通知 → 次日再提；
   未处理超过 3 次自动 dismissed，防止变成每日噪音。
3. 动作写回：complete / snooze / dismiss。
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import get_pool
from app.services import crud

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Shanghai")

# 未处理事件最多提醒次数，超过自动 dismissed
MAX_REMIND_COUNT = 3

# 同步事件时，临期窗口（天）
EXPIRY_WINDOW_DAYS = 3

KIND_LABELS = {
    "expiry": "临期提醒",
    "low_stock": "库存偏低",
    "bill": "交费提醒",
    "maintenance": "维护提醒",
    "todo": "待办",
}


# ============================================================
# 事件同步：库存 → events
# ============================================================

async def sync_inventory_events() -> dict:
    """
    扫描 inventory，把临期/过期/低库存同步为 events。
    每日早报 job 与提醒扫描 job 前都会先跑一次，保证事件数据新鲜。
    """
    now = datetime.now(TZ)
    today = now.date()
    threshold = today + timedelta(days=EXPIRY_WINDOW_DAYS)
    created = updated = resolved = 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        # ---- 临期 / 已过期 ----
        expiring = await conn.fetch(
            """
            SELECT id, name, quantity, unit, location, expiry_date
            FROM inventory
            WHERE expiry_date IS NOT NULL AND expiry_date <= $1
            """,
            threshold,
        )
        for item in expiring:
            expiry = item["expiry_date"]
            expired = expiry < today
            days_left = (expiry - today).days
            title = (
                f"{item['name']} 已过期（{expiry}）"
                if expired
                else f"{item['name']} 还有 {days_left} 天到期（{expiry}）"
            )
            detail = (
                f"库存 {item['quantity']}{item['unit']}"
                + (f"，存放在 {item['location']}" if item["location"] else "")
            )
            payload = {"auto": True, "quantity": int(item["quantity"]), "unit": item["unit"]}

            existing = await crud.get_event_by_ref(conn, "expiry", "inventory", item["id"])
            if existing and existing["status"] in ("pending", "snoozed"):
                # 状态仍活跃 → 更新标题/到期信息（数量、到期日可能变化）
                await crud.update_event_fields(
                    conn, existing["id"], title=title, detail=detail,
                    due_at=datetime(expiry.year, expiry.month, expiry.day, tzinfo=TZ),
                    payload={**(existing.get("payload") or {}), **payload},
                )
                updated += 1
            elif not existing:
                await crud.create_event(
                    conn, kind="expiry", title=title, detail=detail,
                    due_at=datetime(expiry.year, expiry.month, expiry.day, tzinfo=TZ),
                    remind_at=now, ref_type="inventory", ref_id=item["id"],
                    payload={**payload, "remind_count": 0},
                )
                created += 1
            # done/dismissed 的不重建：用户已表态，不再骚扰

        # ---- 低库存 ----
        low_stock = await conn.fetch(
            "SELECT id, name, quantity, unit FROM inventory WHERE quantity <= 5"
        )
        for item in low_stock:
            title = f"{item['name']} 库存偏低（剩 {item['quantity']}{item['unit']}）"
            payload = {"auto": True, "quantity": int(item["quantity"]), "unit": item["unit"]}
            existing = await crud.get_event_by_ref(conn, "low_stock", "inventory", item["id"])
            if existing and existing["status"] in ("pending", "snoozed"):
                await crud.update_event_fields(
                    conn, existing["id"], title=title, payload={**(existing.get("payload") or {}), **payload}
                )
                updated += 1
            elif not existing:
                await crud.create_event(
                    conn, kind="low_stock", title=title,
                    remind_at=now, ref_type="inventory", ref_id=item["id"],
                    payload={**payload, "remind_count": 0},
                )
                created += 1

        # ---- 自动解决已不成立的事件（补货后不再低库存、消耗/换新后不再临期） ----
        stale_events = await conn.fetch(
            """
            SELECT e.id, e.kind, e.ref_id
            FROM events e
            WHERE e.status IN ('pending', 'snoozed')
              AND e.ref_type = 'inventory'
              AND (
                (e.kind = 'low_stock' AND NOT EXISTS (
                    SELECT 1 FROM inventory i
                    WHERE i.id = e.ref_id AND i.quantity <= 5))
                OR
                (e.kind = 'expiry' AND NOT EXISTS (
                    SELECT 1 FROM inventory i
                    WHERE i.id = e.ref_id
                      AND i.expiry_date IS NOT NULL AND i.expiry_date <= $1))
              )
            """,
            threshold,
        )
        for e in stale_events:
            await crud.set_event_status(conn, e["id"], "done")
            resolved += 1

    if created or updated or resolved:
        logger.info(f"📋 事件同步完成：新建 {created}，更新 {updated}，自动解决 {resolved}")
    return {"created": created, "updated": updated, "resolved": resolved}


# ============================================================
# 提醒扫描：到点推送 + 次日重提 + 3 次上限
# ============================================================

async def scan_due_reminders() -> int:
    """
    扫描 remind_at 到点的事件并推送。
    - 推送成功 → remind_count+1，remind_at 推到明天（次日再提一次）
    - remind_count 已达 3 次 → 不再提醒，自动 dismissed
    - 没有可用通知渠道时不动事件（下次扫描再试），避免静默消耗提醒次数
    返回实际推送条数。
    """
    from app.services.notifier import get_notifier

    now = datetime.now(TZ)
    pool = await get_pool()
    async with pool.acquire() as conn:
        due = await crud.get_due_reminders(conn, now)

    if not due:
        return 0

    notifier = await get_notifier()
    if notifier is None:
        logger.info("📭 有到点提醒但未配置通知渠道，等待下次扫描")
        return 0

    sent = 0
    async with pool.acquire() as conn:
        for event in due:
            payload = dict(event.get("payload") or {})
            remind_count = int(payload.get("remind_count", 0))

            # 重提次数用尽 → 自动忽略，不再骚扰
            if remind_count >= MAX_REMIND_COUNT:
                payload["auto_dismissed"] = True
                await crud.update_event_fields(conn, event["id"], payload=payload)
                await crud.set_event_status(conn, event["id"], "dismissed")
                logger.info(f"🔇 事件 {event['id']}「{event['title']}」提醒 {remind_count} 次未处理，自动忽略")
                continue

            label = KIND_LABELS.get(event["kind"], "提醒")
            body = event["title"] + (f"\n{event['detail']}" if event.get("detail") else "")
            body += f"\n（第 {remind_count + 1}/{MAX_REMIND_COUNT} 次提醒，可在今日简报里标记完成）"
            ok = await notifier.send(f"🐹 {label}", body, level="warning")

            if ok:
                sent += 1
                payload["remind_count"] = remind_count + 1
                payload["last_reminded_at"] = now.isoformat()
                # 次日再提一次；snoozed 事件也回到 pending（由扫描统一调度）
                await crud.update_event_fields(
                    conn, event["id"], payload=payload, remind_at=now + timedelta(days=1)
                )
                await crud.set_event_status(conn, event["id"], "pending")

    if sent:
        logger.info(f"🔔 提醒扫描完成：推送 {sent} 条")
    return sent


# ============================================================
# 动作写回
# ============================================================

async def complete_event(event_id: int) -> dict | None:
    """标记事件完成"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.set_event_status(conn, event_id, "done")


async def snooze_event(event_id: int, hours: float = 24.0) -> dict | None:
    """稍后提醒：状态置 snoozed，remind_at 顺延指定小时数"""
    now = datetime.now(TZ)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await crud.update_event_fields(conn, event_id, remind_at=now + timedelta(hours=hours))
        return await crud.set_event_status(conn, event_id, "snoozed")


async def dismiss_event(event_id: int) -> dict | None:
    """忽略事件（用户明确表态，不再提醒）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.set_event_status(conn, event_id, "dismissed")
