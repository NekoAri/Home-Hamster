-- ============================================================
-- HomeHamster 家庭管理 Agent - 数据库初始化脚本
-- 数据库: PostgreSQL 15+ (需安装 pgvector 插件)
-- ============================================================

-- 启用 pgvector 扩展（用于向量存储，支撑 Agent 长期记忆与语义检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_trgm 扩展（用于模糊搜索，如物品名称模糊匹配）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 1. 物品类别表（item_categories）
--    用于管理物品的分类体系，如"食品"、"日用品"、"药品"等
-- ============================================================
CREATE TABLE IF NOT EXISTS item_categories (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100)   NOT NULL,              -- 类别名称
    code        VARCHAR(50)    NOT NULL UNIQUE,       -- 类别编号（唯一）
    description TEXT,                                 -- 类别描述
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 为类别名称建立索引用于模糊搜索
CREATE INDEX IF NOT EXISTS idx_item_categories_name_trgm
    ON item_categories USING gin (name gin_trgm_ops);

-- ============================================================
-- 2. 账本表（ledgers）
--    支持多账本分账管理，如日常开销、家庭公共、旅行基金等
-- ============================================================
CREATE TABLE IF NOT EXISTS ledgers (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100)   NOT NULL,                   -- 账本名称
    icon        VARCHAR(20)     DEFAULT '📔',               -- 账本图标(emoji)
    color       VARCHAR(20)     DEFAULT 'orange',           -- 显示颜色
    description TEXT,                                        -- 账本描述
    is_default  BOOLEAN         NOT NULL DEFAULT FALSE,     -- 是否默认账本
    sort_order  INTEGER         NOT NULL DEFAULT 0,         -- 排序权重
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. 账目表（accounts）
--    记录家庭收支流水，包含金额、分类、时间、备注等
--    ledger_id 关联账本，实现多账本分账管理
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id          BIGSERIAL PRIMARY KEY,
    amount      NUMERIC(12, 2) NOT NULL,              -- 金额（正数为收入，负数为支出）
    category    VARCHAR(50)    NOT NULL,              -- 分类（如 餐饮/交通/工资/购物 等）
    type        VARCHAR(10)    NOT NULL DEFAULT 'expense', -- 类型: expense(支出) / income(收入)
    ledger_id   BIGINT          NOT NULL DEFAULT 1,    -- 所属账本ID（外键 -> ledgers.id）
    occurred_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(), -- 发生时间
    note        TEXT,                                 -- 备注
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_accounts_ledger FOREIGN KEY (ledger_id) REFERENCES ledgers(id) ON DELETE RESTRICT
);

-- 为账目时间建立索引，便于按时间段查询
CREATE INDEX IF NOT EXISTS idx_accounts_occurred_at
    ON accounts (occurred_at DESC);

-- 为账目分类建立索引，便于按分类统计
CREATE INDEX IF NOT EXISTS idx_accounts_category
    ON accounts (category);

-- 为账目类型建立索引，便于区分收支
CREATE INDEX IF NOT EXISTS idx_accounts_type
    ON accounts (type);

-- 为账目账本建立索引，便于按账本筛选
CREATE INDEX IF NOT EXISTS idx_accounts_ledger_id
    ON accounts (ledger_id);

-- ============================================================
-- 3. 物品仓储表（inventory）
--    管理家庭物品库存，支持条码、类别关联、JSONB 自定义属性
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200)  NOT NULL,            -- 物品名称
    barcode         VARCHAR(100),                      -- 物品条码（可空）
    category_id     BIGINT,                            -- 关联物品类别表
    quantity        INTEGER       NOT NULL DEFAULT 0,  -- 数量
    unit            VARCHAR(20)   NOT NULL DEFAULT '个', -- 单位（个/箱/瓶/kg 等）
    location        VARCHAR(100),                      -- 存放位置（如"厨房柜子"、"冰箱"）
    expiry_date     DATE,                              -- 过期时间
    custom_attrs    JSONB         NOT NULL DEFAULT '{}', -- 自定义属性（JSONB，灵活存储）
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 外键约束：类别必须存在
    CONSTRAINT fk_inventory_category
        FOREIGN KEY (category_id) REFERENCES item_categories(id)
        ON DELETE SET NULL
);

-- 为物品名称建立模糊搜索索引
CREATE INDEX IF NOT EXISTS idx_inventory_name_trgm
    ON inventory USING gin (name gin_trgm_ops);

-- 为物品条码建立索引
CREATE INDEX IF NOT EXISTS idx_inventory_barcode
    ON inventory (barcode);

-- 为物品类别建立索引
CREATE INDEX IF NOT EXISTS idx_inventory_category_id
    ON inventory (category_id);

-- 为物品位置建立索引
CREATE INDEX IF NOT EXISTS idx_inventory_location
    ON inventory (location);

-- 为过期时间建立索引（便于查询即将过期物品）
CREATE INDEX IF NOT EXISTS idx_inventory_expiry_date
    ON inventory (expiry_date);

-- 为 custom_attrs 建立 GIN 索引（支持 JSONB 键值查询）
CREATE INDEX IF NOT EXISTS idx_inventory_custom_attrs_gin
    ON inventory USING gin (custom_attrs);

-- ============================================================
-- 4. 用户偏好 / Agent 记忆表（agent_memories）
--    使用 pgvector 存储记忆向量，用于长期记忆与对话历史的语义检索
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_memories (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(100)  NOT NULL DEFAULT 'default', -- 用户标识
    memory_type     VARCHAR(30)   NOT NULL,                  -- 记忆类型: preference(偏好) / conversation(对话) / fact(事实)
    content         TEXT          NOT NULL,                  -- 记忆文本内容
    embedding       vector(768),                             -- 向量嵌入（本地 nomic-embed-text-v1.5 维度为 768；老库由 ensure 自动迁移）
    metadata        JSONB         NOT NULL DEFAULT '{}',     -- 附加元数据
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 为用户 ID 建立索引
CREATE INDEX IF NOT EXISTS idx_agent_memories_user_id
    ON agent_memories (user_id);

-- 为记忆类型建立索引
CREATE INDEX IF NOT EXISTS idx_agent_memories_type
    ON agent_memories (memory_type);

-- 为向量字段建立 HNSW 索引（支持高效的近似最近邻搜索）
-- 使用余弦距离（vector_cosine_ops），适合语义相似度检索
CREATE INDEX IF NOT EXISTS idx_agent_memories_embedding_hnsw
    ON agent_memories USING hnsw (embedding vector_cosine_ops);

-- 为 metadata 建立 GIN 索引
CREATE INDEX IF NOT EXISTS idx_agent_memories_metadata_gin
    ON agent_memories USING gin (metadata);

-- ============================================================
-- 5. 自动更新 updated_at 触发器
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为各表创建 updated_at 自动更新触发器
CREATE TRIGGER trigger_item_categories_updated_at
    BEFORE UPDATE ON item_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_ledgers_updated_at
    BEFORE UPDATE ON ledgers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_inventory_updated_at
    BEFORE UPDATE ON inventory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_agent_memories_updated_at
    BEFORE UPDATE ON agent_memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 5.1 LLM 大模型配置表（llm_configs）
--    支持多供应商配置，用户可从前端动态配置不同的 LLM
--    支持: openai / anthropic / ollama / deepseek / zhipu / azure / custom 等
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_configs (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(100)  NOT NULL,               -- 配置名称（如 "我的 GPT-4o"、"本地 Ollama"）
    provider        VARCHAR(50)   NOT NULL,              -- 供应商: openai / anthropic / ollama / deepseek / zhipu / azure / custom
    api_key         TEXT          NOT NULL DEFAULT '',    -- API 密钥（Ollama 等本地模型可为空）
    base_url        VARCHAR(500),                        -- API 基础 URL（如 https://api.openai.com/v1）
    model_name      VARCHAR(100)  NOT NULL,              -- 模型名称（如 gpt-4o-mini / claude-3-5-sonnet / qwen2:7b）
    embedding_model VARCHAR(100),                        -- 嵌入模型名称（可选，用于向量记忆）
    temperature     NUMERIC(3,2)  NOT NULL DEFAULT 0.70,  -- 采样温度（0.00 ~ 2.00）
    max_tokens      INTEGER      NOT NULL DEFAULT 4096,  -- 最大输出 token 数
    is_active       BOOLEAN      NOT NULL DEFAULT FALSE, -- 是否为当前激活的配置
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 为 is_active 建立索引（快速查找当前激活配置）
CREATE INDEX IF NOT EXISTS idx_llm_configs_is_active
    ON llm_configs (is_active);

-- ============================================================
-- 5.2 Agent 人设配置表（agent_configs）
--    用户可配置 Agent 的名字、头像、性格、系统提示词等
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_configs (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(50)   NOT NULL,               -- Agent 名字（如 "仓鼠管家"）
    avatar          VARCHAR(20)   NOT NULL DEFAULT '🐹',  -- Agent 头像（emoji 或 URL）
    personality     TEXT          NOT NULL DEFAULT '',    -- 性格描述（如 "友好、简洁、有幽默感"）
    system_prompt   TEXT,                                -- 自定义系统提示词（可选，为空时自动从 name+personality 生成）
    llm_config_id   BIGINT,                              -- 关联使用的 LLM 配置（为空时使用默认 is_active 的 LLM）
    temperature     NUMERIC(3,2)  NOT NULL DEFAULT 0.70,  -- 对话采样温度（覆盖 LLM 配置中的温度）
    is_active       BOOLEAN      NOT NULL DEFAULT FALSE, -- 是否为当前激活的 Agent 人设
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 外键约束：关联的 LLM 配置必须存在
    CONSTRAINT fk_agent_configs_llm
        FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)
        ON DELETE SET NULL
);

-- 为 is_active 建立索引
CREATE INDEX IF NOT EXISTS idx_agent_configs_is_active
    ON agent_configs (is_active);

-- ============================================================
-- 5.3 为新表创建 updated_at 触发器
-- ============================================================
CREATE TRIGGER trigger_llm_configs_updated_at
    BEFORE UPDATE ON llm_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_agent_configs_updated_at
    BEFORE UPDATE ON agent_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 5.4 对话会话表（chat_sessions）
--    管理用户与 Agent 的对话会话，支持多会话切换
--    包含历史消息摘要，用于滑动窗口上下文压缩
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(100)  NOT NULL UNIQUE,             -- 会话唯一标识（UUID，前端生成）
    user_id         VARCHAR(100)  NOT NULL DEFAULT 'default',  -- 用户标识
    title           VARCHAR(200),                              -- 会话标题（自动从首条消息生成）
    summary         TEXT          NOT NULL DEFAULT '',          -- 历史消息摘要（超过滑动窗口时自动生成）
    message_count   INTEGER       NOT NULL DEFAULT 0,           -- 消息总数
    is_archived     BOOLEAN       NOT NULL DEFAULT FALSE,       -- 是否归档
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 为用户 ID 建立索引
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
    ON chat_sessions (user_id);

-- 为更新时间建立索引（按最近会话排序）
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at
    ON chat_sessions (updated_at DESC);

-- ============================================================
-- 5.5 对话消息表（chat_messages）
--    持久化存储每条对话消息，支持从数据库重建上下文
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(100)  NOT NULL,                     -- 关联会话
    role            VARCHAR(20)   NOT NULL,                     -- 角色: user / assistant / tool
    content         TEXT          NOT NULL DEFAULT '',           -- 消息内容
    tool_calls      JSONB,                                      -- 工具调用信息（assistant 消息可能携带）
    tool_call_id    VARCHAR(100),                               -- 工具调用 ID（tool 角色消息）
    token_count     INTEGER       NOT NULL DEFAULT 0,            -- 估算的 token 数
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 外键约束：消息必须属于已存在的会话
    CONSTRAINT fk_chat_messages_session
        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        ON DELETE CASCADE
);

-- 为会话 ID 建立索引
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
    ON chat_messages (session_id);

-- 为会话 ID + 创建时间建立联合索引（按时间顺序加载历史消息）
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_time
    ON chat_messages (session_id, created_at);

-- ============================================================
-- 5.6 为新表创建 updated_at 触发器
-- ============================================================
CREATE TRIGGER trigger_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 6. 初始数据（可选）
-- ============================================================
INSERT INTO item_categories (name, code, description) VALUES
    ('食品', 'FOOD', '食品类，包括零食、饮料、调味品等'),
    ('日用品', 'DAILY', '日常用品，包括纸巾、洗护用品等'),
    ('药品', 'MEDICINE', '药品及保健品'),
    ('电子产品', 'ELECTRONICS', '电子产品及配件'),
    ('衣物', 'CLOTHING', '衣物及鞋帽'),
    ('其他', 'OTHER', '未分类物品')
ON CONFLICT (code) DO NOTHING;

-- 插入默认 Agent 人设配置（使用仓鼠管家形象）
INSERT INTO agent_configs (name, avatar, personality, system_prompt, is_active)
VALUES (
    '仓鼠管家',
    '🐹',
    '友好、亲切、简洁实用，像一个精明能干的家庭管家。偶尔带一点幽默感。',
    NULL,
    TRUE
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 5.7 Agent 模型绑定表（agent_model_bindings）
--    主从架构下，为主 Agent 与各子 Agent 分别指定使用的 LLM 配置。
--    agent_key: master(主 Agent) / 子 Agent 注册表中的 key（如 bookkeeping、inventory）
--    未出现在此表中的子 Agent 回退使用主 Agent 的模型配置。
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_model_bindings (
    agent_key     VARCHAR(50) PRIMARY KEY,        -- Agent 标识: master / bookkeeping / inventory ...
    llm_config_id BIGINT      NOT NULL,           -- 关联的 LLM 配置
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_agent_model_bindings_llm
        FOREIGN KEY (llm_config_id) REFERENCES llm_configs(id)
        ON DELETE CASCADE
);

-- ============================================================
-- 7. 事件表（events）
--     通用事件模型：临期/低库存/账单/维护/待办 统一落在这里，
--     支撑每日早报、提醒闭环与后续的日程待办功能。
--     不为任何单一功能写死字段，扩展信息放 payload。
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    kind        VARCHAR(30)   NOT NULL,              -- 事件类型: expiry / low_stock / bill / maintenance / todo
    title       VARCHAR(200)  NOT NULL,              -- 事件标题（通知中直接展示）
    detail      TEXT,                                -- 详细描述（可选）
    due_at      TIMESTAMPTZ,                         -- 到期时间（何时该做）
    remind_at   TIMESTAMPTZ,                         -- 提醒时间（何时该说）
    repeat_rule VARCHAR(100),                        -- 重复规则（RRULE 片段或简单关键词，如 daily/weekly）
    status      VARCHAR(20)   NOT NULL DEFAULT 'pending', -- 状态: pending / done / snoozed / dismissed
    ref_type    VARCHAR(50),                         -- 关联对象类型（如 inventory / account / chat_session）
    ref_id      BIGINT,                              -- 关联对象 ID
    owner_id    VARCHAR(100)  NOT NULL DEFAULT 'default', -- 家庭成员标识
    payload     JSONB         NOT NULL DEFAULT '{}', -- 附加信息（如物品数量、账单金额快照）
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 提醒时间索引（调度器扫描"该提醒了"的事件）
CREATE INDEX IF NOT EXISTS idx_events_remind_at
    ON events (remind_at);

-- 状态 + 提醒时间联合索引（调度器主查询：pending 且到点）
CREATE INDEX IF NOT EXISTS idx_events_status_remind_at
    ON events (status, remind_at);

-- 关联对象索引（从对象反查事件，如"牛奶"对应的事件标记完成）
CREATE INDEX IF NOT EXISTS idx_events_ref
    ON events (ref_type, ref_id);

CREATE TRIGGER trigger_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 8. 通知渠道表（notify_channels）
--     存放通知适配器配置（Bark / 企业微信机器人 等），
--     type 决定用哪个 Notifier 实现，config 为该渠道的参数。
-- ============================================================
CREATE TABLE IF NOT EXISTS notify_channels (
    id          BIGSERIAL PRIMARY KEY,
    type        VARCHAR(30)   NOT NULL UNIQUE,       -- 渠道类型: bark / wecom_bot / console（同类型仅一条）
    name        VARCHAR(100)  NOT NULL DEFAULT '',   -- 渠道名称（如"我的 iPhone"）
    config      JSONB         NOT NULL DEFAULT '{}', -- 渠道参数（如 Bark 的 server + device_key）
    enabled     BOOLEAN       NOT NULL DEFAULT FALSE, -- 是否启用
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trigger_notify_channels_updated_at
    BEFORE UPDATE ON notify_channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 9. 成员维度（owner_id）
--     为关键业务表补家庭成员维度，默认 'default'。
--     本期只铺字段与默认值，不做权限、不做多用户登录。
-- ============================================================
ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(100) NOT NULL DEFAULT 'default';
ALTER TABLE inventory
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(100) NOT NULL DEFAULT 'default';
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(100) NOT NULL DEFAULT 'default';

-- ============================================================
-- 10. 每日早报表（daily_reports）
--     规则聚合 + LLM 润色 + 发送记录，一份结构贯穿推送与前端展示。
--     report_date 唯一：同一自然日只发一次（幂等去重的落点）。
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_reports (
    id            BIGSERIAL PRIMARY KEY,
    report_date   DATE          NOT NULL UNIQUE,        -- 早报日期（自然日，Asia/Shanghai）
    template_text TEXT          NOT NULL,               -- 规则聚合的结构化摘要（模板版）
    polished_text TEXT,                                 -- LLM 润色稿（LLM 不可用时为空）
    is_polished   BOOLEAN       NOT NULL DEFAULT FALSE, -- 是否成功润色
    status        VARCHAR(20)   NOT NULL DEFAULT 'pending', -- 状态: pending / sent / failed
    fail_reason   TEXT,                                 -- 发送失败原因（可选）
    trigger_type  VARCHAR(20)   NOT NULL DEFAULT 'scheduled', -- 触发方式: scheduled / manual
    data          JSONB         NOT NULL DEFAULT '{}',  -- 原始聚合数据（金额/库存数字的来源，前端可复用）
    sent_at       TIMESTAMPTZ,                          -- 实际发送时间
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trigger_daily_reports_updated_at
    BEFORE UPDATE ON daily_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 11. 应用设置表（app_settings）
--     简单 KV：存早报开关/时间等应用级配置（与 Agent 人设分离）。
--     value 为 JSONB，便于存结构化配置且免频繁改表。
-- ============================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key        VARCHAR(100) PRIMARY KEY,
    value      JSONB         NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
