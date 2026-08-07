"""
HomeHamster Agent 工具服务
定义供 LLM Function Calling 调用的工具函数
"""

from app.services import crud
from app.database import get_pool
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 工具函数定义
# 这些函数会被 LLM 通过 Function Calling 调用
# ============================================================

async def add_expense(
    amount: float,
    category: str,
    note: str = "",
    expense_type: str = "expense",
    ledger_name: str = "",
) -> str:
    """
    添加一条账目记录（支出或收入）

    Args:
        amount: 金额（正数）
        category: 分类（如 餐饮/交通/工资/购物 等）
        note: 备注信息
        expense_type: 类型，expense(支出) 或 income(收入)
        ledger_name: 账本名称（如"日常开销"、"旅行基金"等），为空则记到默认账本

    Returns:
        操作结果描述
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 解析账本
            ledger_id = None
            ledger_label = "默认账本"
            if ledger_name:
                ledger = await crud.get_ledger_by_name(conn, ledger_name)
                if ledger:
                    ledger_id = ledger["id"]
                    ledger_label = f"{ledger['icon']} {ledger['name']}"
                else:
                    return f"❌ 未找到名为「{ledger_name}」的账本，请先创建账本或使用正确的账本名称。"

            # 如果是支出，金额转为负数存储
            actual_amount = -abs(amount) if expense_type == "expense" else abs(amount)
            record = await crud.create_account(
                conn,
                amount=actual_amount,
                category=category,
                type=expense_type,
                ledger_id=ledger_id,
                note=note,
            )
            return (
                f"✅ 已记账：{'支出' if expense_type == 'expense' else '收入'} ¥{abs(amount):.2f}"
                f" | 分类: {category} | 账本: {ledger_label}"
                f" | 备注: {note or '无'} | ID: {record['id']}"
            )
    except Exception as e:
        logger.error(f"添加账目失败: {e}")
        return f"❌ 添加账目失败: {str(e)}"


async def check_expense(
    start_date: str = "",
    end_date: str = "",
    category: str = "",
    expense_type: str = "",
    ledger_name: str = "",
    limit: int = 50,
) -> str:
    """
    查询家庭账目记录和消费统计

    Args:
        start_date: 开始日期（格式 YYYY-MM-DD），为空则默认本月1号
        end_date: 结束日期（格式 YYYY-MM-DD），为空则默认今天
        category: 账目分类筛选（如餐饮、交通等），为空则查全部分类
        expense_type: 类型筛选：expense(仅支出) 或 income(仅收入)，为空则查全部
        ledger_name: 账本名称筛选（如"日常开销"、"旅行基金"等），为空则查全部账本
        limit: 返回明细记录数量上限，默认50

    Returns:
        账目统计摘要 + 明细列表的格式化字符串
    """
    try:
        # 解析日期参数
        from datetime import datetime as dt

        now = dt.now()
        dt_start = None
        dt_end = None

        if start_date:
            try:
                dt_start = dt.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return f"❌ start_date 格式错误，请使用 YYYY-MM-DD 格式，如 2026-08-01"

        if end_date:
            try:
                dt_end = dt.strptime(end_date, "%Y-%m-%d")
                # 结束日期设为当天结束（23:59:59）
                dt_end = dt_end.replace(hour=23, minute=59, second=59)
            except ValueError:
                return f"❌ end_date 格式错误，请使用 YYYY-MM-DD 格式，如 2026-08-31"

        # 默认查询本月
        if not dt_start:
            dt_start = dt(now.year, now.month, 1)
        if not dt_end:
            dt_end = now

        type_filter = expense_type if expense_type in ("expense", "income") else None
        cat_filter = category if category else None

        pool = await get_pool()
        async with pool.acquire() as conn:
            # 解析账本
            ledger_id = None
            ledger_label = "全部账本"
            if ledger_name:
                ledger = await crud.get_ledger_by_name(conn, ledger_name)
                if ledger:
                    ledger_id = ledger["id"]
                    ledger_label = f"{ledger['icon']} {ledger['name']}"
                else:
                    return f"❌ 未找到名为「{ledger_name}」的账本。可用的账本请通过 list_ledgers 工具查看。"

            # 获取统计摘要
            summary = await crud.get_accounts_summary(conn, ledger_id=ledger_id, start_date=dt_start, end_date=dt_end)

            # 获取明细列表
            total_count = await crud.count_accounts(
                conn,
                category=cat_filter,
                type=type_filter,
                ledger_id=ledger_id,
                start_date=dt_start,
                end_date=dt_end,
            )

            records = await crud.list_accounts(
                conn,
                limit=limit,
                category=cat_filter,
                type=type_filter,
                ledger_id=ledger_id,
                start_date=dt_start,
                end_date=dt_end,
            )

        logger.info(
            f"check_expense 调用: start={dt_start.date()}, end={dt_end.date()}, "
            f"category={category!r}, type={expense_type!r}, ledger={ledger_name!r} → {total_count} 条记录"
        )

        # 构建返回文本
        lines = []
        lines.append(f"💰 账目统计（{dt_start.strftime('%Y-%m-%d')} ~ {dt_end.strftime('%Y-%m-%d')}）账本: {ledger_label}\n")
        lines.append(f"  📊 总支出: ¥{summary['total_expense']:.2f}（{summary['expense_count']} 笔）")
        lines.append(f"  📊 总收入: ¥{summary['total_income']:.2f}（{summary['income_count']} 笔）")
        lines.append(f"  📊 净额: {'+' if summary['net_amount'] >= 0 else ''}¥{summary['net_amount']:.2f}")

        # 支出分类明细
        if summary["expense_by_category"]:
            lines.append(f"\n  📋 支出分类:")
            for c in summary["expense_by_category"]:
                pct = (c["total"] / summary["total_expense"] * 100) if summary["total_expense"] > 0 else 0
                lines.append(f"    • {c['category']}: ¥{c['total']:.2f}（{c['count']} 笔，{pct:.1f}%）")

        # 收入分类明细
        if summary["income_by_category"]:
            lines.append(f"\n  📋 收入分类:")
            for c in summary["income_by_category"]:
                lines.append(f"    • {c['category']}: ¥{c['total']:.2f}（{c['count']} 笔）")

        # 明细列表
        if records:
            lines.append(f"\n📝 明细记录（共 {total_count} 条，显示 {len(records)} 条）:")
            for r in records:
                amt = abs(float(r["amount"]))
                type_label = "支出" if r["type"] == "expense" else "收入"
                occurred = r["occurred_at"]
                if hasattr(occurred, "strftime"):
                    occurred_str = occurred.strftime("%m-%d %H:%M")
                else:
                    occurred_str = str(occurred)[:11]
                note_str = f" | 备注: {r['note']}" if r.get("note") else ""
                ledger_str = f" | 账本: {r.get('ledger_name', '?')}" if not ledger_id else ""
                lines.append(
                    f"  • [{occurred_str}] {type_label} ¥{amt:.2f} | 分类: {r['category']}{ledger_str}{note_str}"
                )

            if total_count > len(records):
                lines.append(f"\n⚠️ 还有 {total_count - len(records)} 条记录未显示。")
        else:
            lines.append("\n📝 该时间段内暂无账目记录。")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"查询账目失败: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ 查询账目失败: {str(e)}"


async def inventory_type(
    name: str,
    code: str,
    description: str = "",
) -> str:
    """
    新增物品类别

    Args:
        name: 类别名称（如"食品"、"日用品"）
        code: 类别编号（唯一标识，如"FOOD"、"DAILY"）
        description: 类别描述

    Returns:
        操作结果描述
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            record = await crud.create_category(
                conn,
                name=name,
                code=code,
                description=description,
            )
            return (
                f"✅ 类别已添加：{name}({code})"
                + (f" | 描述: {description}" if description else "")
                + f" | ID: {record['id']}"
            )
    except Exception as e:
        logger.error(f"添加物品类别失败: {e}")
        return f"❌ 添加物品类别失败: {str(e)}"


async def check_inventory(
    name: str = "",
    location: str = "",
    barcode: str = "",
    limit: int = 50,
) -> str:
    """
    查询物品库存信息

    Args:
        name: 物品名称（支持模糊搜索）
        location: 存放位置（支持模糊搜索）
        barcode: 物品条码（精确匹配）
        limit: 返回结果数量上限

    Returns:
        物品库存列表的格式化字符串
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 先查总数
            total_count = await crud.count_inventory(
                conn,
                name=name if name else None,
                location=location if location else None,
                barcode=barcode if barcode else None,
            )

            items = await crud.list_inventory(
                conn,
                limit=limit,
                name=name if name else None,
                location=location if location else None,
                barcode=barcode if barcode else None,
            )

            logger.info(f"check_inventory 调用: name={name!r}, location={location!r}, barcode={barcode!r}, limit={limit} → 返回 {len(items)}/{total_count} 条")

            if not items:
                return "📦 未找到匹配的物品库存记录。"

            result_lines = [f"📦 共找到 {total_count} 条物品记录（本次返回 {len(items)} 条）：\n"]
            for item in items:
                expiry_str = ""
                if item.get("expiry_date"):
                    expiry_str = f" | 过期日期: {item['expiry_date']}"

                category_str = item.get("category_name") or "未分类"

                result_lines.append(
                    f"  • {item['name']} (ID:{item['id']})\n"
                    f"    数量: {item['quantity']}{item['unit']} | "
                    f"位置: {item.get('location') or '未指定'} | "
                    f"类别: {category_str}{expiry_str}"
                )

            if total_count > len(items):
                result_lines.append(f"\n⚠️ 还有 {total_count - len(items)} 条记录未显示，请增大 limit 参数查看全部。")

            return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"查询物品库存失败: {e}")
        return f"❌ 查询物品库存失败: {str(e)}"


async def list_ledgers() -> str:
    """
    查询所有账本列表（含统计信息）

    Returns:
        账本列表的格式化字符串，包含每个账本的名称、图标、记录数、支出和收入
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            ledgers = await crud.list_ledgers(conn, include_stats=True)

            if not ledgers:
                return "📔 当前没有任何账本，请先创建账本。"

            lines = [f"📔 共有 {len(ledgers)} 个账本：\n"]
            for l in ledgers:
                default_tag = " (默认)" if l["is_default"] else ""
                expense = abs(float(l["total_expense"]))
                income = float(l["total_income"])
                lines.append(
                    f"  • {l['icon']} {l['name']}{default_tag}\n"
                    f"    记录数: {l['record_count']} | 总支出: ¥{expense:.2f} | 总收入: ¥{income:.2f}"
                )
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"查询账本列表失败: {e}")
        return f"❌ 查询账本列表失败: {str(e)}"


async def add_purchase(
    item_name: str,
    quantity: float,
    unit: str,
    amount: float,
    category: str = "",
    location: str = "",
    ledger_name: str = "",
    note: str = "",
) -> str:
    """
    记录一笔购物消费，同时录入/更新物品库存。当用户购买物品时（如"买了一箱牛奶花了60元"），调用此工具一次性完成记账和入库。

    Args:
        item_name: 物品名称（如"牛奶"、"抽纸"）
        quantity: 购买数量
        unit: 单位（如"箱"、"瓶"、"包"、"个"）
        amount: 花费金额（正数）
        category: 账目分类（如"购物"、"食品"），为空则默认"购物"
        location: 存放位置（如"厨房"、"冰箱"），为空则不设置
        ledger_name: 账本名称，为空则记到默认账本
        note: 备注

    Returns:
        操作结果描述（记账+入库）
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. 记账
            ledger_id = None
            ledger_label = "默认账本"
            if ledger_name:
                ledger = await crud.get_ledger_by_name(conn, ledger_name)
                if ledger:
                    ledger_id = ledger["id"]
                    ledger_label = f"{ledger['icon']} {ledger['name']}"
                else:
                    return f"❌ 未找到名为「{ledger_name}」的账本。"

            cat = category or "购物"
            actual_amount = -abs(amount)
            await crud.create_account(
                conn,
                amount=actual_amount,
                category=cat,
                type="expense",
                ledger_id=ledger_id,
                note=note or f"购买{item_name}",
            )

            # 2. 入库（同名物品累加数量）
            existing = await crud.get_inventory_by_name(conn, item_name)
            if existing:
                new_qty = float(existing["quantity"]) + quantity
                await crud.update_inventory(
                    conn,
                    existing["id"],
                    quantity=new_qty,
                    location=location or existing.get("location") or None,
                )
                inv_action = f"库存已更新：{item_name} {existing['quantity']}{existing['unit']} → {new_qty}{unit}"
            else:
                await crud.create_inventory(
                    conn,
                    name=item_name,
                    quantity=quantity,
                    unit=unit,
                    location=location or None,
                )
                inv_action = f"新物品已入库：{item_name} {quantity}{unit}"

            logger.info(f"add_purchase: {item_name} x{quantity}{unit} ¥{amount} | 账本={ledger_label}")

            return (
                f"✅ 已记账+入库\n"
                f"  支出 ¥{amount:.2f} → {ledger_label}（{cat}）\n"
                f"  {inv_action}"
            )
    except Exception as e:
        logger.error(f"add_purchase 失败: {e}")
        return f"❌ 操作失败: {str(e)}"


async def add_inventory(
    name: str,
    quantity: float,
    unit: str = "个",
    location: str = "",
    note: str = "",
) -> str:
    """
    添加或补充物品库存（不涉及记账）。当用户想录入已有物品、补充库存、登记家中现有物品时调用。

    Args:
        name: 物品名称
        quantity: 数量
        unit: 单位（如"个"、"瓶"、"箱"、"包"）
        location: 存放位置（如"厨房"、"冰箱"）
        note: 备注

    Returns:
        操作结果描述
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            existing = await crud.get_inventory_by_name(conn, name)
            if existing:
                new_qty = float(existing["quantity"]) + quantity
                await crud.update_inventory(
                    conn,
                    existing["id"],
                    quantity=new_qty,
                    location=location or existing.get("location") or None,
                )
                return f"✅ 库存已更新：{name} {existing['quantity']}{existing['unit']} → {new_qty}{unit}"
            else:
                await crud.create_inventory(
                    conn,
                    name=name,
                    quantity=quantity,
                    unit=unit,
                    location=location or None,
                )
                return f"✅ 新物品已入库：{name} {quantity}{unit}"
    except Exception as e:
        logger.error(f"add_inventory 失败: {e}")
        return f"❌ 操作失败: {str(e)}"


# ============================================================
# OpenAI Function Calling 工具定义
# 将上面的函数定义为 OpenAI tools 格式，供 Agent 使用
# ============================================================

# OpenAI 格式的工具定义（OpenAI / DeepSeek / Ollama / 智谱 等兼容供应商通用）
# Anthropic 供应商会在 llm_provider.py 中自动转换格式
TOOLS_DEFINITION_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "add_purchase",
            "description": "记录一笔购物消费，同时自动录入或更新物品库存。当用户说买了某样东西、采购物品、购物消费时（如'买了一箱牛奶花了60元'、'买了2包纸巾30元'），调用此工具一次性完成记账和入库。如果用户只是花钱但没有具体物品（如打车、交水电费），用 add_expense 而非此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "物品名称，如：牛奶、抽纸、大米",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "购买数量",
                    },
                    "unit": {
                        "type": "string",
                        "description": "单位，如：箱、瓶、包、个、袋",
                    },
                    "amount": {
                        "type": "number",
                        "description": "花费金额（正数），如 60.5",
                    },
                    "category": {
                        "type": "string",
                        "description": "账目分类，如：购物、食品、日用品。不传则默认'购物'。",
                    },
                    "location": {
                        "type": "string",
                        "description": "存放位置，如：厨房、冰箱、卧室。不传则不设置。",
                    },
                    "ledger_name": {
                        "type": "string",
                        "description": "账本名称，如：日常开销、家庭公共。不传则记到默认账本。",
                    },
                    "note": {
                        "type": "string",
                        "description": "备注信息",
                    },
                },
                "required": ["item_name", "quantity", "unit", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "添加一条家庭账目记录（支出或收入），可指定账本。当用户提到消费、花钱、收入、记账等操作，但不涉及具体物品采购时调用此工具。如打车、交水电费、发工资等。涉及购买具体物品时请用 add_purchase。",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "金额（正数），例如 50.5 表示 50.5 元",
                    },
                    "category": {
                        "type": "string",
                        "description": "账目分类，如：餐饮、交通、购物、工资、娱乐、医疗、教育、住房等",
                    },
                    "note": {
                        "type": "string",
                        "description": "备注信息，如消费的具体内容",
                    },
                    "expense_type": {
                        "type": "string",
                        "enum": ["expense", "income"],
                        "description": "类型：expense=支出，income=收入。默认为 expense",
                    },
                    "ledger_name": {
                        "type": "string",
                        "description": "账本名称，如：日常开销、家庭公共、旅行基金、孩子教育、投资理财。不传则记到默认账本。可通过 list_ledgers 工具查看所有账本。",
                    },
                },
                "required": ["amount", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_expense",
            "description": "查询家庭账目记录和消费统计，可按账本筛选。当用户想查看花了多少钱、收入情况、消费记录、账目明细、某时间段的支出统计、某个账本的情况时调用此工具。例如'这个月花了多少钱'、'日常开销花了多少'、'旅行基金花了多少'、'上个月消费多少'等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "查询开始日期，格式 YYYY-MM-DD，如 2026-08-01。为空则默认本月1号。",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "查询结束日期，格式 YYYY-MM-DD，如 2026-08-31。为空则默认今天。",
                    },
                    "category": {
                        "type": "string",
                        "description": "按分类筛选，如：餐饮、交通、购物、工资、娱乐、医疗、教育、住房等。为空则查全部分类。",
                    },
                    "expense_type": {
                        "type": "string",
                        "enum": ["expense", "income"],
                        "description": "类型筛选：expense=仅查支出，income=仅查收入。为空则查全部。",
                    },
                    "ledger_name": {
                        "type": "string",
                        "description": "按账本名称筛选，如：日常开销、家庭公共、旅行基金、孩子教育、投资理财。为空则查全部账本。可通过 list_ledgers 工具查看所有账本。",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回明细记录数量上限，默认50。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ledgers",
            "description": "查询所有账本列表（含统计信息）。当用户想知道有哪些账本、每个账本花了多少、各账本的收支情况时调用此工具。例如'我有哪些账本'、'各账本情况'、'旅行基金花了多少'等。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "查询家庭物品库存信息。当用户想知道家里有什么物品、某物品库存多少、某位置的物品时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "物品名称（支持模糊搜索），如：牛奶、纸巾",
                    },
                    "location": {
                        "type": "string",
                        "description": "存放位置，如：厨房、冰箱、卧室",
                    },
                    "barcode": {
                        "type": "string",
                        "description": "物品条码（精确匹配）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量上限，默认50。查询全部库存时不要传此参数或传50。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_inventory",
            "description": "添加或补充物品库存（不涉及记账）。当用户想录入已有物品、补充库存、登记家中现有物品时调用。如'家里还有5包纸巾'、'补充3瓶矿泉水'。涉及花钱购买时请用 add_purchase。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "物品名称，如：牛奶、抽纸",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "数量",
                    },
                    "unit": {
                        "type": "string",
                        "description": "单位，如：个、瓶、箱、包、袋",
                    },
                    "location": {
                        "type": "string",
                        "description": "存放位置，如：厨房、冰箱、卧室",
                    },
                    "note": {
                        "type": "string",
                        "description": "备注信息",
                    },
                },
                "required": ["name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_type",
            "description": "新增物品类别。当用户需要添加新的物品分类时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "类别名称，如：食品、日用品、药品",
                    },
                    "code": {
                        "type": "string",
                        "description": "类别编号（英文大写），如：FOOD、DAILY、MEDICINE",
                    },
                    "description": {
                        "type": "string",
                        "description": "类别描述信息",
                    },
                },
                "required": ["name", "code"],
            },
        },
    },
]


# 工具名称到函数的映射表
TOOL_FUNCTIONS = {
    "add_purchase": add_purchase,
    "add_expense": add_expense,
    "check_expense": check_expense,
    "list_ledgers": list_ledgers,
    "check_inventory": check_inventory,
    "add_inventory": add_inventory,
    "inventory_type": inventory_type,
}

# 向后兼容别名
TOOLS_DEFINITION = TOOLS_DEFINITION_OPENAI
