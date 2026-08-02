"""
HomeHamster Pydantic 数据模型 / Schema 定义
用于请求参数校验和响应数据序列化
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, Any


# ============================================================
# 账目相关 Schema
# ============================================================

class AccountCreate(BaseModel):
    """创建账目请求"""
    amount: float = Field(..., description="金额（正数收入，负数支出）")
    category: str = Field(..., max_length=50, description="分类")
    type: str = Field("expense", description="类型: expense(支出) / income(收入)")
    occurred_at: Optional[datetime] = Field(None, description="发生时间，默认当前时间")
    note: Optional[str] = Field(None, description="备注")


class AccountUpdate(BaseModel):
    """更新账目请求"""
    amount: Optional[float] = None
    category: Optional[str] = Field(None, max_length=50)
    type: Optional[str] = None
    occurred_at: Optional[datetime] = None
    note: Optional[str] = None


class AccountResponse(BaseModel):
    """账目响应"""
    id: int
    amount: float
    category: str
    type: str
    occurred_at: datetime
    note: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================
# 物品类别相关 Schema
# ============================================================

class CategoryCreate(BaseModel):
    """创建物品类别请求"""
    name: str = Field(..., max_length=100, description="类别名称")
    code: str = Field(..., max_length=50, description="类别编号")
    description: Optional[str] = Field(None, description="类别描述")


class CategoryUpdate(BaseModel):
    """更新物品类别请求"""
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    """物品类别响应"""
    id: int
    name: str
    code: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============================================================
# 物品仓储相关 Schema
# ============================================================

class InventoryCreate(BaseModel):
    """创建物品库存请求"""
    name: str = Field(..., max_length=200, description="物品名称")
    barcode: Optional[str] = Field(None, max_length=100, description="物品条码")
    category_id: Optional[int] = Field(None, description="关联类别 ID")
    quantity: int = Field(0, ge=0, description="数量")
    unit: str = Field("个", max_length=20, description="单位")
    location: Optional[str] = Field(None, max_length=100, description="存放位置")
    expiry_date: Optional[date] = Field(None, description="过期时间")
    custom_attrs: dict[str, Any] = Field(default_factory=dict, description="自定义属性")


class InventoryUpdate(BaseModel):
    """更新物品库存请求"""
    name: Optional[str] = Field(None, max_length=200)
    barcode: Optional[str] = Field(None, max_length=100)
    category_id: Optional[int] = None
    quantity: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[date] = None
    custom_attrs: Optional[dict[str, Any]] = None


class InventoryResponse(BaseModel):
    """物品库存响应"""
    id: int
    name: str
    barcode: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str] = None
    quantity: int
    unit: str
    location: Optional[str]
    expiry_date: Optional[date]
    custom_attrs: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ============================================================
# Agent 对话相关 Schema
# ============================================================

class ChatMessage(BaseModel):
    """对话消息"""
    role: str = Field(..., description="角色: user / assistant / tool")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """Agent 对话请求"""
    messages: list[ChatMessage] = Field(..., description="对话历史")
    user_id: str = Field("default", description="用户标识")


# ============================================================
# LLM 配置相关 Schema
# ============================================================

class LLMConfigCreate(BaseModel):
    """创建 LLM 配置请求"""
    name: str = Field(..., max_length=100, description="配置名称")
    provider: str = Field(..., max_length=50, description="供应商: openai/anthropic/ollama/deepseek/zhipu/custom")
    api_key: str = Field("", description="API 密钥")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    model_name: str = Field(..., max_length=100, description="模型名称")
    embedding_model: Optional[str] = Field(None, description="嵌入模型名称")
    temperature: float = Field(0.7, ge=0, le=2, description="采样温度")
    max_tokens: int = Field(4096, ge=1, description="最大 token 数")
    is_active: bool = Field(False, description="是否激活")


class LLMConfigUpdate(BaseModel):
    """更新 LLM 配置请求"""
    name: Optional[str] = Field(None, max_length=100)
    provider: Optional[str] = Field(None, max_length=50)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = Field(None, max_length=100)
    embedding_model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    """LLM 配置响应（列表展示时不返回完整 api_key）"""
    id: int
    name: str
    provider: str
    api_key: str  # 返回时会被截断处理
    base_url: Optional[str]
    model_name: str
    embedding_model: Optional[str]
    temperature: float
    max_tokens: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================
# Agent 人设配置相关 Schema
# ============================================================

class AgentConfigCreate(BaseModel):
    """创建 Agent 人设配置请求"""
    name: str = Field(..., max_length=50, description="Agent 名字")
    avatar: str = Field("🐹", max_length=20, description="Agent 头像 emoji")
    personality: str = Field("", description="性格描述")
    system_prompt: Optional[str] = Field(None, description="自定义系统提示词")
    llm_config_id: Optional[int] = Field(None, description="关联 LLM 配置 ID")
    temperature: float = Field(0.7, ge=0, le=2, description="对话温度")
    is_active: bool = Field(False, description="是否激活")


class AgentConfigUpdate(BaseModel):
    """更新 Agent 人设配置请求"""
    name: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = Field(None, max_length=20)
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_config_id: Optional[int] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    is_active: Optional[bool] = None


class AgentConfigResponse(BaseModel):
    """Agent 人设配置响应"""
    id: int
    name: str
    avatar: str
    personality: str
    system_prompt: Optional[str]
    llm_config_id: Optional[int]
    temperature: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
