"""
每日早报服务

设计约定（P1）：
- 内容全部来自数据库真实查询（临期/已过期、低库存、本月支出对比、未来 3 天到期事件），
  金额与库存数字不允许 LLM 推算或补全。
- 生成策略：规则聚合模板为主，LLM 只做润色；LLM 不可用/超时/报错时直接发模板版，
  绝不因此不发。
- 幂等：daily_reports.report_date 唯一，同一自然日的定时触发只发一次；
  重启服务后依据已落库的 sent 状态跳过，不会重复发送。
  手动触发（force=True）不受此限制，方便验收与调试。
- 可关闭：app_settings.morning_report.enabled=False 时定时任务不再生成早报。
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from app.database import get_pool
from app.services import crud
from app.services.notifier import get_notifier

logger = logging.getLogger(__name__)

# 业务时区（与调度器一致）
TZ = ZoneInfo("Asia/Shanghai")

# 早报设置在 app_settings 中的键
SETTINGS_KEY = "morning_report"

DEFAULT_SETTINGS = {"enabled": True, "hour": 8, "minute": 0}

# 展示条数上限（避免早报变成清单轰炸）
MAX_EXPIRED = 3
MAX_EXPIRING = 3
MAX_LOW_STOCK = 3
MAX_EVENTS = 3


# ============================================================
# 设置读写
# ============================================================

def normalize_settings(value: dict | None) -> dict:
    """校验并归一化早报设置，非法值回退默认"""
    s = dict(DEFAULT_SETTINGS)
    if not isinstance(value, dict):
        return s
    if isinstance(value.get("enabled"), bool):
        s["enabled"] = value["enabled"]
    try:
        h = int(value.get("hour", s["hour"]))
        m = int(value.get("minute", s["minute"]))
        if 0 <= h <= 23:
            s["hour"] = h
        if 0 <= m <= 59:
            s["minute"] = m
    except (TypeError, ValueError):
        pass
    return s


async def load_settings() -> dict:
    """读取早报设置（无记录/读取失败时用默认值）"""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            value = await crud.get_app_setting(conn, SETTINGS_KEY)
        return normalize_settings(value)
    except Exception as e:
        logger.error(f"读取早报设置失败，使用默认值: {e}")
        return dict(DEFAULT_SETTINGS)


async def save_settings(value: dict) -> dict:
    """保存早报设置（归一化后落库），返回实际保存的值"""
    normalized = normalize_settings(value)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await crud.set_app_setting(conn, SETTINGS_KEY, normalized)
    return normalized


# ============================================================
# 数据聚合（全部来自数据库查询）
# ============================================================

async def collect_report_data(conn) -> dict:
    """
    聚合早报所需的全部真实数据：
    - 已过期物品、3 天内到期物品
    - 低库存物品（数量 <= 5）
    - 本月支出 vs 上月同期支出
    - 未来 3 天到期的 pending 事件
    """
    now = datetime.now(TZ)
    today = now.date()
    in_3_days = today + timedelta(days=3)

    # ---- 库存：已过期 ----
    expired = await conn.fetch(
        """
        SELECT name, quantity, unit, location, expiry_date
        FROM inventory
        WHERE expiry_date IS NOT NULL AND expiry_date < $1
        ORDER BY expiry_date ASC LIMIT $2
        """,
        today, MAX_EXPIRED,
    )

    # ---- 库存：3 天内到期（含今天） ----
    expiring = await conn.fetch(
        """
        SELECT name, quantity, unit, location, expiry_date
        FROM inventory
        WHERE expiry_date IS NOT NULL AND expiry_date >= $1 AND expiry_date <= $2
        ORDER BY expiry_date ASC LIMIT $3
        """,
        today, in_3_days, MAX_EXPIRING,
    )

    # ---- 低库存 ----
    low_stock = await conn.fetch(
        """
        SELECT name, quantity, unit
        FROM inventory WHERE quantity <= 5
        ORDER BY quantity ASC LIMIT $1
        """,
        MAX_LOW_STOCK,
    )

    # ---- 支出对比：本月累计 vs 上月同期 ----
    month_start = today.replace(day=1)
    prev_month_last_day = month_start - timedelta(days=1)
    prev_month_start = prev_month_last_day.replace(day=1)
    prev_same_day = prev_month_start + timedelta(days=(today - month_start).days)

    this_month_row = await conn.fetchrow(
        "SELECT COALESCE(SUM(ABS(amount)), 0) AS total FROM accounts "
        "WHERE type = 'expense' AND occurred_at >= $1 AND occurred_at < $2",
        datetime(month_start.year, month_start.month, month_start.day, tzinfo=TZ), now,
    )
    prev_month_row = await conn.fetchrow(
        "SELECT COALESCE(SUM(ABS(amount)), 0) AS total FROM accounts "
        "WHERE type = 'expense' AND occurred_at >= $1 AND occurred_at < $2",
        datetime(prev_month_start.year, prev_month_start.month, prev_month_start.day, tzinfo=TZ),
        datetime(prev_same_day.year, prev_same_day.month, prev_same_day.day, tzinfo=TZ)
        + timedelta(days=1),
    )
    this_month_expense = round(float(this_month_row["total"]), 2)
    prev_month_expense = round(float(prev_month_row["total"]), 2)

    # ---- 未来 3 天到期的事件（pending） ----
    events = await conn.fetch(
        """
        SELECT kind, title, detail, due_at
        FROM events
        WHERE status = 'pending'
          AND due_at IS NOT NULL
          AND due_at >= $1 AND due_at < $2
        ORDER BY due_at ASC LIMIT $3
        """,
        datetime(now.year, now.month, now.day, tzinfo=TZ),
        datetime(in_3_days.year, in_3_days.month, in_3_days.day, tzinfo=TZ) + timedelta(days=1),
        MAX_EVENTS,
    )

    return {
        "report_date": today.isoformat(),
        "expired": [_fmt_item(r) for r in expired],
        "expiring": [_fmt_item(r) for r in expiring],
        "low_stock": [
            {"name": r["name"], "quantity": int(r["quantity"]), "unit": r["unit"]}
            for r in low_stock
        ],
        "expense": {
            "this_month": this_month_expense,
            "prev_month_same_period": prev_month_expense,
        },
        "events": [
            {
                "kind": r["kind"],
                "title": r["title"],
                "due_date": r["due_at"].date().isoformat() if r["due_at"] else None,
            }
            for r in events
        ],
    }


def _fmt_item(row) -> dict:
    """统一库存条目的展示字段"""
    return {
        "name": row["name"],
        "quantity": int(row["quantity"]),
        "unit": row["unit"],
        "location": row["location"] or "",
        "expiry_date": row["expiry_date"].isoformat() if row["expiry_date"] else None,
    }


# ============================================================
# 模板构建（管家口吻，简洁不卖萌）
# ============================================================

def build_template(data: dict) -> str:
    """把聚合数据拼成结构化的模板文本"""
    today = date.fromisoformat(data["report_date"])
    lines = [f"早上好，今天是 {today.month} 月 {today.day} 日。"]

    expired, expiring = data.get("expired") or [], data.get("expiring") or []
    if expired:
        names = "、".join(f"{i['name']}（{i['quantity']}{i['unit']}）" for i in expired)
        lines.append(f"有 {len(expired)} 样东西已过期，建议处理：{names}。")
    if expiring:
        parts = []
        for i in expiring:
            d = date.fromisoformat(i["expiry_date"])
            days = (d - today).days
            when = "今天到期" if days == 0 else f"{days} 天后到期"
            parts.append(f"{i['name']}（{when}）")
        lines.append(f"注意保质期：{'、'.join(parts)}。")

    low = data.get("low_stock") or []
    if low:
        parts = "、".join(f"{i['name']}（剩 {i['quantity']}{i['unit']}）" for i in low)
        lines.append(f"库存偏低，记得补货：{parts}。")

    exp = data.get("expense") or {}
    this_m, prev_m = exp.get("this_month", 0.0), exp.get("prev_month_same_period", 0.0)
    if this_m > 0 or prev_m > 0:
        if prev_m > 0:
            diff = round(this_m - prev_m, 2)
            if diff > 0:
                lines.append(
                    f"本月支出 ¥{this_m:.2f}，比上月同期多 ¥{diff:.2f}。"
                )
            elif diff < 0:
                lines.append(
                    f"本月支出 ¥{this_m:.2f}，比上月同期少 ¥{abs(diff):.2f}。"
                )
            else:
                lines.append(f"本月支出 ¥{this_m:.2f}，与上月同期持平。")
        else:
            lines.append(f"本月支出 ¥{this_m:.2f}。")

    events = data.get("events") or []
    if events:
        kind_label = {"bill": "交费", "todo": "待办", "maintenance": "维护",
                      "expiry": "到期", "low_stock": "补货"}
        parts = []
        for e in events:
            label = kind_label.get(e["kind"], "事项")
            due = e.get("due_date") or ""
            parts.append(f"{label}「{e['title']}」{f'（{due}）' if due else ''}")
        lines.append(f"接下来几天的事：{'；'.join(parts)}。")

    if len(lines) == 1:
        lines.append("家里一切正常，没什么需要操心的。")
    else:
        lines.append("详情可以在「今日简报」里查看。")

    return "\n".join(lines)


# ============================================================
# LLM 润色（可选，失败不影响发送）
# ============================================================

POLISH_SYSTEM_PROMPT = (
    "你是家庭管家的文案助手。把给你的早报要点改写成 2-3 句自然、简洁的中文，"
    "像一位靠谱的管家在早上跟主人交代事情。"
    "严格保留原文中的所有数字（金额、数量、日期、物品名），不允许增删或修改任何数字和事实；"
    "没有提到的内容不要编造。直接输出正文，不要加标题和称呼。"
)


async def polish_with_llm(template_text: str) -> str | None:
    """用主 Agent 的 LLM 润色早报；任何异常/超时返回 None（回退模板版）"""
    try:
        from app.services.agent_manager import AgentManager

        provider = await AgentManager.get_instance().get_provider()
        if provider is None:
            return None

        async def _do():
            chunks = []
            async for chunk in provider.chat_stream(
                [
                    {"role": "system", "content": POLISH_SYSTEM_PROMPT},
                    {"role": "user", "content": template_text},
                ],
                # 润色是工具型调用，关闭推理模型思考链，避免超时
                extra_body={"reasoning_effort": "none"},
            ):
                if chunk:
                    chunks.append(chunk)
            return "".join(chunks).strip()

        polished = await asyncio.wait_for(_do(), timeout=90)
        # 润色结果过短或异常长都视为失败，回退模板
        if not polished or len(polished) < 10 or len(polished) > 500:
            logger.warning("LLM 润色结果异常，回退模板版")
            return None
        return polished
    except asyncio.TimeoutError:
        logger.warning("LLM 润色超时（90s），回退模板版")
        return None
    except Exception as e:
        logger.warning(f"LLM 润色失败，回退模板版: {e}")
        return None


# ============================================================
# 生成 + 发送主流程
# ============================================================

async def generate_and_send(force: bool = False, trigger: str = "scheduled") -> dict:
    """
    生成当日早报并推送。

    返回:
        {
            "ok": bool,               # 是否成功推送
            "message": str,           # 给调用方看的结果说明
            "text": str,              # 实际发送的正文
            "is_polished": bool,      # 是否 LLM 润色版
            "skipped": bool,          # 是否因幂等跳过
        }
    """
    today = datetime.now(TZ).date()

    # ---- 幂等检查：今天定时触发已发过则跳过（手动 force 除外） ----
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await crud.get_daily_report(conn, today)
        if (
            not force
            and trigger == "scheduled"
            and existing
            and existing["status"] == "sent"
        ):
            return {
                "ok": True,
                "message": "今天的早报已经发过了，不重复发送",
                "text": existing.get("polished_text") or existing["template_text"],
                "is_polished": bool(existing.get("is_polished")),
                "skipped": True,
            }

        # ---- 1. 规则聚合（真实数据） ----
        data = await collect_report_data(conn)
        template_text = build_template(data)

    # ---- 2. LLM 润色（可失败，失败用模板） ----
    polished_text = await polish_with_llm(template_text)
    send_text = polished_text or template_text
    is_polished = polished_text is not None

    # ---- 3. 推送 ----
    notifier = await get_notifier()
    if notifier is None:
        reason = "未配置启用的通知渠道（设置 → 通知渠道）"
        async with pool.acquire() as conn:
            await crud.upsert_daily_report(
                conn, today, template_text, polished_text, is_polished,
                status="failed", trigger_type=trigger, data=data, fail_reason=reason,
            )
        logger.warning(f"早报未发送: {reason}")
        return {"ok": False, "message": reason, "text": send_text,
                "is_polished": is_polished, "skipped": False}

    ok = await notifier.send("🐹 今日简报", send_text, level="info")
    status = "sent" if ok else "failed"
    fail_reason = None if ok else "通知渠道发送失败"

    # ---- 4. 落库（幂等标记 + 历史记录） ----
    async with pool.acquire() as conn:
        record = await crud.upsert_daily_report(
            conn, today, template_text, polished_text, is_polished,
            status=status, trigger_type=trigger, data=data,
            fail_reason=fail_reason,
            sent_at=datetime.now(TZ) if ok else None,
        )

    if ok:
        logger.info(f"📮 {today} 早报已发送（{'润色版' if is_polished else '模板版'}，{trigger}）")
        return {"ok": True, "message": "今日简报已发送", "text": send_text,
                "is_polished": is_polished, "skipped": False}

    logger.warning(f"早报发送失败: {fail_reason}")
    return {"ok": False, "message": fail_reason, "text": send_text,
            "is_polished": is_polished, "skipped": False}


async def scheduled_morning_report() -> None:
    """调度器入口：开关关闭时不做任何事"""
    settings = await load_settings()
    if not settings.get("enabled"):
        logger.info("早报功能已关闭，跳过本次触发")
        return
    await generate_and_send(force=False, trigger="scheduled")
