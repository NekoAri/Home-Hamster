"""
HomeHamster Agent 工具服务
定义供 LLM Function Calling 调用的工具函数
"""

from app.services import crud
from app.database import get_pool
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
) -> str:
    """
    添加一条账目记录（支出或收入）

    Args:
        amount: 金额（正数）
        category: 分类（如 餐饮/交通/工资/购物 等）
        note: 备注信息
        expense_type: 类型，expense(支出) 或 income(收入)

    Returns:
        操作结果描述
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 如果是支出，金额转为负数存储
            actual_amount = -abs(amount) if expense_type == "expense" else abs(amount)
            record = await crud.create_account(
                conn,
                amount=actual_amount,
                category=category,
                type=expense_type,
                note=note,
            )
            return (
                f"✅ 账目已添加成功！\n"
                f"  - 类型: {'支出' if expense_type == 'expense' else '收入'}\n"
                f"  - 金额: ¥{abs(amount):.2f}\n"
                f"  - 分类: {category}\n"
                f"  - 备注: {note or '无'}\n"
                f"  - 记录ID: {record['id']}"
            )
    except Exception as e:
        logger.error(f"添加账目失败: {e}")
        return f"❌ 添加账目失败: {str(e)}"


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
                f"✅ 物品类别已添加成功！\n"
                f"  - 类别名称: {name}\n"
                f"  - 类别编号: {code}\n"
                f"  - 描述: {description or '无'}\n"
                f"  - 类别ID: {record['id']}"
            )
    except Exception as e:
        logger.error(f"添加物品类别失败: {e}")
        return f"❌ 添加物品类别失败: {str(e)}"


async def check_inventory(
    name: str = "",
    location: str = "",
    barcode: str = "",
    limit: int = 10,
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
            items = await crud.list_inventory(
                conn,
                limit=limit,
                name=name if name else None,
                location=location if location else None,
                barcode=barcode if barcode else None,
            )

            if not items:
                return "📦 未找到匹配的物品库存记录。"

            result_lines = [f"📦 共找到 {len(items)} 条物品记录：\n"]
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

            return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"查询物品库存失败: {e}")
        return f"❌ 查询物品库存失败: {str(e)}"


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
            "name": "add_expense",
            "description": "添加一条家庭账目记录（支出或收入）。当用户提到消费、花钱、收入、记账等操作时调用此工具。",
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
                },
                "required": ["amount", "category"],
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
                        "description": "返回结果数量上限，默认10",
                    },
                },
            },
        },
    },
]


# 工具名称到函数的映射表
TOOL_FUNCTIONS = {
    "add_expense": add_expense,
    "inventory_type": inventory_type,
    "check_inventory": check_inventory,
}

# 向后兼容别名
TOOLS_DEFINITION = TOOLS_DEFINITION_OPENAI
