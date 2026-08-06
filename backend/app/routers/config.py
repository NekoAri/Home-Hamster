"""
配置管理路由
提供 LLM 配置和 Agent 人设配置的 CRUD API
以及供应商预设信息查询（供前端下拉选择）

v3 改进：配置变更后自动触发 AgentManager 热重载
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from app.models import (
    LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse,
    AgentConfigCreate, AgentConfigUpdate, AgentConfigResponse,
)
from app.services import crud
from app.services.llm_provider import PROVIDER_PRESETS
from app.services.agent_manager import AgentManager
from app.database import get_pool

router = APIRouter(prefix="/api/configs", tags=["配置管理"])


async def _reload_agent():
    """配置变更后触发 AgentManager 热重载（非阻塞，失败不影响操作结果）"""
    try:
        await AgentManager.get_instance().reload()
    except Exception as e:
        # 热重载失败不影响配置操作本身，下次对话时会自动重新加载
        pass


# ============================================================
# 供应商预设信息（前端下拉选择用）
# ============================================================

@router.get("/providers", summary="获取支持的供应商列表")
async def get_providers():
    """返回所有支持的 LLM 供应商信息，前端用此接口渲染供应商下拉框"""
    return PROVIDER_PRESETS


# ============================================================
# LLM 配置 CRUD
# ============================================================

@router.post("/llm", response_model=LLMConfigResponse, summary="创建 LLM 配置")
async def create_llm_config(config: LLMConfigCreate):
    """创建一条 LLM 供应商配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await crud.create_llm_config(
            conn,
            name=config.name,
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            model_name=config.model_name,
            embedding_model=config.embedding_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            is_active=config.is_active,
        )
    if config.is_active:
        await _reload_agent()
    return result


@router.get("/llm", response_model=list[LLMConfigResponse], summary="查询所有 LLM 配置")
async def list_llm_configs():
    """查询所有 LLM 配置列表"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        configs = await crud.list_llm_configs(conn)
        for c in configs:
            key = c.get("api_key", "")
            if key and len(key) > 12:
                c["api_key"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
        return configs


@router.get("/llm/active", response_model=Optional[LLMConfigResponse], summary="获取当前激活的 LLM 配置")
async def get_active_llm():
    """获取当前激活的 LLM 配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await crud.get_active_llm_config(conn)
        if not config:
            return None
        key = config.get("api_key", "")
        if key and len(key) > 12:
            config["api_key"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
        return config


@router.put("/llm/{config_id}", response_model=LLMConfigResponse, summary="更新 LLM 配置")
async def update_llm_config(config_id: int, config: LLMConfigUpdate):
    """更新 LLM 配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        update_data = config.model_dump(exclude_unset=True)
        if update_data.get("api_key") and "*" in update_data["api_key"]:
            del update_data["api_key"]

        record = await crud.update_llm_config(conn, config_id, **update_data)
        if not record:
            raise HTTPException(status_code=404, detail="LLM 配置不存在")
        key = record.get("api_key", "")
        if key and len(key) > 12:
            record["api_key"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
    await _reload_agent()
    return record


@router.delete("/llm/{config_id}", summary="删除 LLM 配置")
async def delete_llm_config(config_id: int):
    """删除 LLM 配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_llm_config(conn, config_id)
        if not success:
            raise HTTPException(status_code=404, detail="LLM 配置不存在")
    await _reload_agent()
    return {"message": "删除成功", "id": config_id}


@router.post("/llm/{config_id}/activate", summary="激活 LLM 配置")
async def activate_llm(config_id: int):
    """将指定 LLM 配置设为当前激活"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await crud.activate_llm_config(conn, config_id)
        if not result:
            raise HTTPException(status_code=404, detail="LLM 配置不存在")
    await _reload_agent()
    return {"message": "已激活", "config": result}


# ============================================================
# Agent 人设配置 CRUD
# ============================================================

@router.post("/agent", response_model=AgentConfigResponse, summary="创建 Agent 人设配置")
async def create_agent_config(config: AgentConfigCreate):
    """创建 Agent 人设配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await crud.create_agent_config(
            conn,
            name=config.name,
            avatar=config.avatar,
            personality=config.personality,
            system_prompt=config.system_prompt,
            llm_config_id=config.llm_config_id,
            temperature=config.temperature,
            is_active=config.is_active,
        )
    if config.is_active:
        await _reload_agent()
    return result


@router.get("/agent", response_model=list[AgentConfigResponse], summary="查询所有 Agent 人设配置")
async def list_agent_configs():
    """查询所有 Agent 人设配置列表"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.list_agent_configs(conn)


@router.get("/agent/active", response_model=Optional[AgentConfigResponse], summary="获取当前激活的 Agent 人设")
async def get_active_agent():
    """获取当前激活的 Agent 人设配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await crud.get_active_agent_config(conn)


@router.put("/agent/{config_id}", response_model=AgentConfigResponse, summary="更新 Agent 人设配置")
async def update_agent_config(config_id: int, config: AgentConfigUpdate):
    """更新 Agent 人设配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        record = await crud.update_agent_config(conn, config_id, **config.model_dump(exclude_unset=True))
        if not record:
            raise HTTPException(status_code=404, detail="Agent 配置不存在")
    await _reload_agent()
    return record


@router.delete("/agent/{config_id}", summary="删除 Agent 人设配置")
async def delete_agent_config(config_id: int):
    """删除 Agent 人设配置"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        success = await crud.delete_agent_config(conn, config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Agent 配置不存在")
    await _reload_agent()
    return {"message": "删除成功", "id": config_id}


@router.post("/agent/{config_id}/activate", summary="激活 Agent 人设配置")
async def activate_agent(config_id: int):
    """将指定 Agent 人设配置设为当前激活"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await crud.activate_agent_config(conn, config_id)
        if not result:
            raise HTTPException(status_code=404, detail="Agent 配置不存在")
    await _reload_agent()
    return {"message": "已激活", "config": result}
