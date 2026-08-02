<div align="center">

<img src="logo.png" alt="HomeHamster Logo" width="200"/>

# 🐹 HomeHamster

### 你的小仓鼠家庭管理助手

*吱吱！让小仓鼠帮你管好家里的每一分钱和每一件物品吧～*

</div>

---

> 🐹 *"吱吱～你好呀！我是 HomeHamster，你的家庭管理小帮手！*
> *我会帮你记账本、管仓库，还能给你出主意～*
> *不用操心琐事，交给小仓鼠就好啦！"*

---

## 🌟 小仓鼠会什么呀？

| 能力 | 小仓鼠说 |
|------|----------|
| 📊 **双模式切换** | 想跟我聊天就聊天，想自己看表格就看表格～怎么方便怎么来！ |
| 📋 **数据查询页面** | 账目、物品、类别，全都能用小爪子在表格里翻来翻去～ |
| 📈 **统计概览** | 花了多少、还剩多少、什么东西快过期了，小仓鼠全帮你算得清清楚楚！ |
| 🔧 **前端设置面板** | 点点齿轮按钮就能调教小仓鼠～ |
| 🤖 **多供应商 LLM** | OpenAI / Claude / DeepSeek / 智谱 / Ollama 都能接，想用哪个用哪个！ |
| 🐹 **Agent 人设配置** | 给小仓鼠起名字、换头像、定性格，独一无二的小家伙！ |

---

## 🏗️ 小仓鼠的技术底子

| 层级 | 技术栈 |
|------|--------|
| 后端 | Python 3.11+ / FastAPI |
| 数据库 | PostgreSQL 16 + pgvector |
| 前端 | Next.js 14 / React 18 / Tailwind CSS |
| AI 交互 | 多供应商 LLM 适配层 + Vercel AI SDK (SSE 流式) |
| 数据库驱动 | asyncpg (异步，跑得快快哒) |

---

## 📁 小仓鼠的窝长这样

```
HomeHamster/
├── docker-compose.yml              # 🏠 小仓鼠的数据库小窝
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口（小仓鼠的大门）
│   │   ├── config.py                # 配置文件
│   │   ├── database.py              # asyncpg 异步连接池
│   │   ├── models/                  # Pydantic 数据模型
│   │   ├── routers/
│   │   │   ├── agent.py             # Agent 对话接口 (SSE 流式)
│   │   │   ├── config.py            # 配置管理 (LLM + Agent 人设)
│   │   │   ├── account.py           # 账目 CRUD
│   │   │   ├── inventory.py         # 物品仓储 CRUD
│   │   │   ├── category.py          # 物品类别 CRUD
│   │   │   └── summary.py           # 统计概览
│   │   └── services/
│   │       ├── agent_service.py     # Agent 服务 (动态配置加载)
│   │       ├── llm_provider.py      # 多供应商 LLM 适配层
│   │       ├── tools.py             # Function Calling 工具函数
│   │       └── crud.py              # 数据库 CRUD 操作
│   ├── sql/init.sql                 # 建表脚本 (含 pgvector + 配置表)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                         # 前端应用
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Chat.tsx                 # 对话组件 (支持嵌入式布局)
│   │   ├── Dashboard.tsx             # 数据管理容器 + 概览面板
│   │   ├── AccountView.tsx          # 账目管理视图 (表格+筛选+分页)
│   │   ├── InventoryView.tsx        # 物品管理视图 (表格+筛选+分页)
│   │   ├── CategoryView.tsx         # 类别管理视图
│   │   └── Settings.tsx             # 设置弹窗
│   ├── lib/
│   │   └── api.ts                   # API 辅助函数 (含类型定义)
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── package.json
```

---

## 🚀 召唤小仓鼠！

### 第 1 步：给小仓鼠搭个数据库窝 🏠

```bash
docker-compose up -d
```

> 小仓鼠歪了歪头："这是给我住的呀？好暖和～"

### 第 2 步：启动后端服务 ⚙️

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # 配置数据库连接
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> 小仓鼠搓了搓小爪子："后端跑起来啦！吱吱～"

### 第 3 步：启动前端界面 🎨

```bash
cd frontend
npm install
npm run dev
```

> 小仓鼠眨了眨眼睛："打开浏览器看看我吧～"

### 第 4 步：第一次见小仓鼠要做的配置 ⚙️

1. 打开 http://localhost:3000
2. 点击右上角 **⚙️ 设置** 按钮
3. 在「模型配置」Tab 中添加你的 LLM 配置：
   - 选择供应商（OpenAI / Claude / DeepSeek / Ollama 等）
   - 填入 API Key、模型名称
   - 点击「激活」让它生效～
4. 在「Agent 人设」Tab 中给小仓鼠起个名字、选个头像、定个性格吧！

> 小仓鼠满怀期待地看着你："给我起个什么名字好呢？吱吱～"

---

## 🔄 两种模式，怎么舒服怎么来

| 模式 | 小仓鼠的说明 |
|------|-------------|
| **🤖 Agent 对话** | 跟我聊天就行！"记一笔奶茶 15 块" "家里还有几包纸巾？" 我都能搞定～ |
| **📊 数据管理** | 想自己翻翻看也行！仪表盘、账目、物品、类别四个 Tab，想看哪个点哪个～ |

顶部导航栏随时切换，你的选择小仓鼠会记在心里（localStorage）哦！

---

## 🤖 多供应商 LLM 适配

小仓鼠不挑食，这些大模型都能吃：

| 供应商 | Provider | 小仓鼠备注 |
|--------|----------|-----------|
| OpenAI | `openai` | GPT-4o 系列，经典口味～ |
| Anthropic | `anthropic` | Claude 3.5 Sonnet，优雅的口味～ |
| DeepSeek | `deepseek` | DeepSeek-Chat，国产好味道～ |
| 智谱 GLM | `zhipu` | GLM-4，也是国产的哦～ |
| Ollama | `ollama` | 本地部署，自给自足，免费吃到饱！ |
| 自定义 | `custom` | 任何 OpenAI 兼容接口都行，不挑食～ |

适配层通过 `llm_provider.py` 统一抽象：
- `OpenAICompatibleProvider` — 一把覆盖所有 OpenAI 兼容供应商
- `AnthropicProvider` — 单独适配 Claude 的工具调用和消息格式
- `create_provider(config)` — 工厂方法，根据配置生成对应实例

---

## 🗄️ 小仓鼠的记账本

| 表名 | 小仓鼠的说明 |
|------|-------------|
| `accounts` | 账目表 — 每一笔收支都记得清清楚楚，小仓鼠从不糊涂！ |
| `item_categories` | 物品类别表 — 把东西分门别类，小仓鼠的强迫症～ |
| `inventory` | 物品仓储表 — 家里有什么、在哪儿、还剩多少，全知道！(含 JSONB 自定义属性) |
| `agent_memories` | Agent 记忆表 — 小仓鼠的长期记忆，用 pgvector 向量存储，忘不了你～ |
| `llm_configs` | LLM 配置表 — 存着各种大模型的连接方式 |
| `agent_configs` | Agent 人设配置表 — 小仓鼠的性格档案 |

---

## 📡 API 接口一览

### 🤖 Agent 对话
- `POST /api/agent/chat` — SSE 流式对话，跟小仓鼠聊天就靠它！

### ⚙️ 配置管理
- `GET /api/configs/providers` — 看看小仓鼠支持哪些供应商
- `GET /api/configs/llm` — 查询所有 LLM 配置
- `POST /api/configs/llm` — 创建 LLM 配置
- `PUT /api/configs/llm/{id}` — 更新 LLM 配置
- `DELETE /api/configs/llm/{id}` — 删除 LLM 配置
- `POST /api/configs/llm/{id}/activate` — 激活 LLM 配置
- `GET /api/configs/agent` — 查询所有 Agent 人设
- `POST /api/configs/agent` — 创建 Agent 人设
- `PUT /api/configs/agent/{id}` — 更新 Agent 人设
- `DELETE /api/configs/agent/{id}` — 删除 Agent 人设
- `POST /api/configs/agent/{id}/activate` — 激活 Agent 人设

### 📋 账目 / 类别 / 物品仓储 CRUD
详见 http://localhost:8000/docs — 小仓鼠把所有接口都整理好啦～

### 📈 统计概览
- `GET /api/summary/overview` — 总览数据（收支汇总、分类排行、近7天趋势）
- `GET /api/summary/inventory-stats` — 库存统计（总览、低库存预警、临期预警、过期提醒）
- `GET /api/summary/accounts/count` — 账目总数（分页计算用）
- `GET /api/summary/inventory/count` — 物品总数（分页计算用）

---

<div align="center">

### 🐹 吱吱～谢谢你让小仓鼠来帮忙！

*HomeHamster — 用爱管理你的小家*

</div>
