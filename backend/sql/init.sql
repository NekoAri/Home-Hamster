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
-- 2. 账目表（accounts）
--    记录家庭收支流水，包含金额、分类、时间、备注等
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id          BIGSERIAL PRIMARY KEY,
    amount      NUMERIC(12, 2) NOT NULL,              -- 金额（正数为收入，负数为支出）
    category    VARCHAR(50)    NOT NULL,              -- 分类（如 餐饮/交通/工资/购物 等）
    type        VARCHAR(10)    NOT NULL DEFAULT 'expense', -- 类型: expense(支出) / income(收入)
    occurred_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(), -- 发生时间
    note        TEXT,                                 -- 备注
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
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
    embedding       vector(1536),                            -- 向量嵌入（OpenAI text-embedding-3-small 维度为 1536）
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
