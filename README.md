# 🐹 HomeHamster - 家庭管理 Agent

智能家庭管理助手，支持家庭账目管理、物品仓储管理，并能基于数据提供资金使用建议和物品采购建议。

## ✨ v3.0 新特性

| 特性 | 说明 |
|------|------|
| 📊 **双模式切换** | 支持「Agent 对话」与「数据管理」两种模式自由切换，用户可直接通过表格操作数据，无需对话 |
| 📋 **数据查询页面** | 完整的账目管理、物品管理、类别管理界面，含筛选、分页、增删改查 |
| 📈 **统计概览** | 仪表盘展示总支出/收入、分类排行、近7天趋势、库存预警、临期提醒 |
| 🔧 **前端设置面板** | 完整的设置弹窗，可配置 LLM 和 Agent 人设 |
| 🤖 **多供应商 LLM** | 支持 OpenAI / Anthropic Claude / DeepSeek / 智谱 GLM / 本地 Ollama 等，通过数据库存储配置，运行时切换 |
| 🐹 **Agent 人设配置** | 自定义 Agent 名字、头像、性格、系统提示词，不同人设可关联不同 LLM |

## 🏗️ 技术架构

| 层级 | 技术栈 |
|------|--------|
| 后端 | Python 3.11+ / FastAPI |
| 数据库 | PostgreSQL 16 + pgvector |
| 前端 | Next.js 14 / React 18 / Tailwind CSS |
| AI 交互 | 多供应商 LLM 适配层 + Vercel AI SDK (SSE 流式) |
| 数据库驱动 | asyncpg (异步) |

## 📁 项目结构

```
HomeHamster/
├── docker-compose.yml              # PostgreSQL + pgvector 容器编排
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── main.py                  # FastAPI 应用入口
│   │   ├── config.py                # 应用配置 (数据库连接)
│   │   ├── database.py              # asyncpg 异步数据库连接池
│   │   ├── models/                  # Pydantic 数据模型
│   │   ├── routers/
│   │   │   ├── agent.py             # Agent 对话接口 (SSE 流式)
│   │   │   ├── config.py            # 配置管理 (LLM + Agent 人设) [v2]
│   │   │   ├── account.py           # 账目 CRUD
│   │   │   ├── inventory.py         # 物品仓储 CRUD
│   │   │   ├── category.py          # 物品类别 CRUD
│   │   │   └── summary.py           # 📌 统计概览 [v3 新增]
│   │   └── services/
│   │       ├── agent_service.py     # Agent 服务 (动态配置加载) [v2]
│   │       ├── llm_provider.py      # 多供应商 LLM 适配层 [v2]
│   │       ├── tools.py             # Function Calling 工具函数
│   │       └── crud.py              # 数据库 CRUD 操作
│   ├── sql/init.sql                 # 数据库建表脚本 (含 pgvector + 配置表)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                         # 前端应用
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Chat.tsx                 # 对话组件 (支持嵌入式布局) [v3]
│   │   ├── Dashboard.tsx             # 📌 数据管理容器 + 概览面板 [v3 新增]
│   │   ├── AccountView.tsx          # 📌 账目管理视图 (表格+筛选+分页) [v3 新增]
│   │   ├── InventoryView.tsx        # 📌 物品管理视图 (表格+筛选+分页) [v3 新增]
│   │   ├── CategoryView.tsx         # 📌 类别管理视图 [v3 新增]
│   │   └── Settings.tsx             # 设置弹窗 [v2]
│   ├── lib/
│   │   └── api.ts                   # API 辅助函数 (含类型定义)
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── package.json
```

## 🚀 快速开始

### 1. 启动数据库

```bash
docker-compose up -d
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # 配置数据库连接
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 配置 LLM（首次使用必读）

1. 打开 http://localhost:3000
2. 点击右上角 **⚙️ 设置** 按钮
3. 在「模型配置」Tab 中添加 LLM 配置：
   - 选择供应商（OpenAI / Claude / DeepSeek / Ollama 等）
   - 填入 API Key、模型名称等
   - 点击「激活」使其成为当前使用的模型
4. 在「Agent 人设」Tab 中可自定义 Agent 名字、头像、性格

## 🔄 双模式说明

| 模式 | 说明 |
|------|------|
| **Agent 对话** | 通过自然语言与 AI 助手交互，支持语音记账、查库存、获取建议等 |
| **数据管理** | 直接通过表格/表单操作数据，含概览仪表盘、账目管理、物品管理、类别管理四个 Tab |

顶部导航栏可随时切换两种模式，选择会保存在 localStorage 中。

## 🤖 多供应商 LLM 适配

| 供应商 | Provider | 说明 |
|--------|----------|------|
| OpenAI | `openai` | GPT-4o, GPT-4o-mini 等 |
| Anthropic | `anthropic` | Claude 3.5 Sonnet 等 |
| DeepSeek | `deepseek` | DeepSeek-Chat，OpenAI 兼容 |
| 智谱 GLM | `zhipu` | GLM-4，OpenAI 兼容 |
| Ollama | `ollama` | 本地部署，无需 API Key |
| 自定义 | `custom` | 任何 OpenAI 兼容接口 |

适配层通过 `llm_provider.py` 统一抽象：
- `OpenAICompatibleProvider` — 覆盖所有 OpenAI 兼容供应商
- `AnthropicProvider` — 独立适配 Claude 的工具调用和消息格式
- `create_provider(config)` — 工厂方法，根据配置创建实例

## 🗄️ 数据库表结构

| 表名 | 说明 |
|------|------|
| `accounts` | 账目表 - 记录家庭收支流水 |
| `item_categories` | 物品类别表 |
| `inventory` | 物品仓储表 (含 JSONB 自定义属性) |
| `agent_memories` | Agent 记忆表 (pgvector 向量存储) |
| `llm_configs` | 📌 LLM 配置表 [v2 新增] |
| `agent_configs` | 📌 Agent 人设配置表 [v2 新增] |

## 📡 API 接口

### Agent 对话
- `POST /api/agent/chat` - SSE 流式对话

### 配置管理 [v2 新增]
- `GET /api/configs/providers` - 获取支持的供应商列表
- `GET /api/configs/llm` - 查询所有 LLM 配置
- `POST /api/configs/llm` - 创建 LLM 配置
- `PUT /api/configs/llm/{id}` - 更新 LLM 配置
- `DELETE /api/configs/llm/{id}` - 删除 LLM 配置
- `POST /api/configs/llm/{id}/activate` - 激活 LLM 配置
- `GET /api/configs/agent` - 查询所有 Agent 人设
- `POST /api/configs/agent` - 创建 Agent 人设
- `PUT /api/configs/agent/{id}` - 更新 Agent 人设
- `DELETE /api/configs/agent/{id}` - 删除 Agent 人设
- `POST /api/configs/agent/{id}/activate` - 激活 Agent 人设

### 账目 / 类别 / 物品仓储 CRUD
详见 http://localhost:8000/docs

### 统计概览 [v3 新增]
- `GET /api/summary/overview` - 总览数据（收支汇总、分类排行、近7天趋势）
- `GET /api/summary/inventory-stats` - 库存统计（总览、低库存预警、临期预警、过期提醒）
- `GET /api/summary/accounts/count` - 账目总数（分页计算）
- `GET /api/summary/inventory/count` - 物品总数（分页计算）
