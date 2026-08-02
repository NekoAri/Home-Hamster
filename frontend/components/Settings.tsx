'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  getProviders, listLLMConfigs, createLLMConfig, updateLLMConfig,
  deleteLLMConfig, activateLLMConfig,
  listAgentConfigs, createAgentConfig, updateAgentConfig,
  deleteAgentConfig, activateAgentConfig, getActiveAgent,
  type ProviderPreset, type LLMConfig, type AgentConfig,
} from '@/lib/api'

/**
 * HomeHamster 设置弹窗组件
 *
 * 两个功能 Tab：
 * 1. 模型配置 — 管理多供应商 LLM 配置（OpenAI / Claude / DeepSeek / Ollama 等）
 * 2. Agent人设 — 配置 Agent 名字、头像、性格、系统提示词
 */

interface SettingsProps {
  onClose: () => void
  onAgentChange?: (agent: AgentConfig) => void
}

// 常用 emoji 头像选择
const AVATAR_OPTIONS = ['🐹', '🐱', '🐶', '🦊', '🐼', '🐨', '🤖', '👨‍💼', '👩‍💼', '🧙', '🐱‍👤', '🦉']

export default function Settings({ onClose, onAgentChange }: SettingsProps) {
  const [activeTab, setActiveTab] = useState<'llm' | 'agent'>('llm')
  const [providers, setProviders] = useState<Record<string, ProviderPreset>>({})
  const [llmConfigs, setLLMConfigs] = useState<LLMConfig[]>([])
  const [agentConfigs, setAgentConfigs] = useState<AgentConfig[]>([])
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [p, llms, agents] = await Promise.all([
        getProviders(),
        listLLMConfigs(),
        listAgentConfigs(),
      ])
      setProviders(p)
      setLLMConfigs(llms)
      setAgentConfigs(agents)
    } catch (e) {
      console.error('加载配置失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-2xl h-[85vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            ⚙️ 设置
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tab 切换 */}
        <div className="flex border-b border-gray-100">
          <button
            onClick={() => setActiveTab('llm')}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${
              activeTab === 'llm'
                ? 'text-orange-500 border-b-2 border-orange-500 bg-orange-50/50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            🤖 模型配置
          </button>
          <button
            onClick={() => setActiveTab('agent')}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${
              activeTab === 'agent'
                ? 'text-orange-500 border-b-2 border-orange-500 bg-orange-50/50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            🐹 Agent 人设
          </button>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto chat-scrollbar">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="w-8 h-8 border-2 border-orange-300 border-t-orange-500 rounded-full animate-spin" />
            </div>
          ) : activeTab === 'llm' ? (
            <LLMConfigTab
              providers={providers}
              configs={llmConfigs}
              onRefresh={loadData}
            />
          ) : (
            <AgentConfigTab
              configs={agentConfigs}
              llmConfigs={llmConfigs}
              onRefresh={loadData}
              onAgentChange={onAgentChange}
            />
          )}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// LLM 模型配置 Tab
// ============================================================

interface LLMConfigTabProps {
  providers: Record<string, ProviderPreset>
  configs: LLMConfig[]
  onRefresh: () => void
}

function LLMConfigTab({ providers, configs, onRefresh }: LLMConfigTabProps) {
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<LLMConfig | null>(null)
  const [form, setForm] = useState({
    name: '',
    provider: 'openai',
    api_key: '',
    base_url: '',
    model_name: '',
    temperature: 0.7,
    max_tokens: 4096,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // 当选择供应商时，自动填充默认值
  const handleProviderChange = (provider: string) => {
    const preset = providers[provider]
    if (preset) {
      setForm({
        ...form,
        provider,
        base_url: preset.default_base_url,
        model_name: preset.default_model,
      })
    } else {
      setForm({ ...form, provider })
    }
  }

  const startEdit = (config: LLMConfig) => {
    setEditing(config)
    setForm({
      name: config.name,
      provider: config.provider,
      api_key: config.api_key,
      base_url: config.base_url || '',
      model_name: config.model_name,
      temperature: config.temperature,
      max_tokens: config.max_tokens,
    })
    setShowForm(true)
  }

  const startCreate = () => {
    setEditing(null)
    const preset = providers['openai']
    setForm({
      name: '',
      provider: 'openai',
      api_key: '',
      base_url: preset?.default_base_url || '',
      model_name: preset?.default_model || '',
      temperature: 0.7,
      max_tokens: 4096,
    })
    setShowForm(true)
    setError('')
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const data = { ...form, is_active: false }
      if (editing) {
        await updateLLMConfig(editing.id, data)
      } else {
        await createLLMConfig(data)
      }
      setShowForm(false)
      setEditing(null)
      onRefresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleActivate = async (id: number) => {
    try {
      await activateLLMConfig(id)
      onRefresh()
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此配置？')) return
    try {
      await deleteLLMConfig(id)
      onRefresh()
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="p-6 space-y-4">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          配置大语言模型供应商，支持多种供应商切换
        </p>
        {!showForm && (
          <button
            onClick={startCreate}
            className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm rounded-lg font-medium transition-colors"
          >
            + 添加配置
          </button>
        )}
      </div>

      {/* 表单 */}
      {showForm && (
        <div className="bg-gray-50 rounded-xl p-5 space-y-4 border border-gray-200">
          <h3 className="font-semibold text-gray-700 text-sm">
            {editing ? '编辑配置' : '新增配置'}
          </h3>

          {/* 供应商选择 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">供应商</label>
            <select
              value={form.provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none bg-white"
            >
              {Object.entries(providers).map(([key, p]) => (
                <option key={key} value={key}>
                  {p.label} — {p.description}
                </option>
              ))}
            </select>
          </div>

          {/* 配置名称 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">配置名称</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：我的 GPT-4o"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
            />
          </div>

          {/* API Key */}
          {providers[form.provider]?.needs_api_key !== false && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">API Key</label>
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder="sk-..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
              />
            </div>
          )}

          {/* Base URL */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Base URL</label>
            <input
              type="text"
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">留空则使用供应商默认地址</p>
          </div>

          {/* 模型名称 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">模型名称</label>
            <input
              type="text"
              value={form.model_name}
              onChange={(e) => setForm({ ...form, model_name: e.target.value })}
              placeholder="gpt-4o-mini"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
            />
          </div>

          {/* 温度和 Max Tokens */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                温度 ({form.temperature})
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={form.temperature}
                onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                className="w-full accent-orange-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">Max Tokens</label>
              <input
                type="number"
                value={form.max_tokens}
                onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) || 4096 })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
              />
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</div>
          )}

          {/* 表单操作按钮 */}
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setEditing(null); setError('') }}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !form.name || !form.model_name}
              className="px-4 py-2 text-sm bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      {/* 配置列表 */}
      <div className="space-y-2">
        {configs.length === 0 && !showForm ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-4xl mb-2">🤖</div>
            <p className="text-sm">还没有配置任何模型，点击「添加配置」开始</p>
          </div>
        ) : (
          configs.map((config) => (
            <div
              key={config.id}
              className={`flex items-center justify-between p-3 rounded-xl border transition-colors ${
                config.is_active
                  ? 'border-orange-300 bg-orange-50'
                  : 'border-gray-200 bg-white hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-3 flex-1">
                <span className="text-xl">
                  {config.provider === 'anthropic' ? '🧠' :
                   config.provider === 'ollama' ? '🖥️' :
                   config.provider === 'deepseek' ? '🔍' :
                   config.provider === 'zhipu' ? '🌟' : '🤖'}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{config.name}</span>
                    {config.is_active && (
                      <span className="text-xs px-2 py-0.5 bg-orange-500 text-white rounded-full">
                        已激活
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">
                    {providers[config.provider]?.label || config.provider} · {config.model_name}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {!config.is_active && (
                  <button
                    onClick={() => handleActivate(config.id)}
                    className="px-3 py-1.5 text-xs text-orange-600 hover:bg-orange-100 rounded-lg transition-colors"
                  >
                    激活
                  </button>
                )}
                <button
                  onClick={() => startEdit(config)}
                  className="px-3 py-1.5 text-xs text-blue-600 hover:bg-blue-100 rounded-lg transition-colors"
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(config.id)}
                  className="px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ============================================================
// Agent 人设配置 Tab
// ============================================================

interface AgentConfigTabProps {
  configs: AgentConfig[]
  llmConfigs: LLMConfig[]
  onRefresh: () => void
  onAgentChange?: (agent: AgentConfig) => void
}

function AgentConfigTab({ configs, llmConfigs, onRefresh, onAgentChange }: AgentConfigTabProps) {
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<AgentConfig | null>(null)
  const [form, setForm] = useState({
    name: '',
    avatar: '🐹',
    personality: '',
    system_prompt: '',
    llm_config_id: null as number | null,
    temperature: 0.7,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const startEdit = (config: AgentConfig) => {
    setEditing(config)
    setForm({
      name: config.name,
      avatar: config.avatar,
      personality: config.personality,
      system_prompt: config.system_prompt || '',
      llm_config_id: config.llm_config_id,
      temperature: config.temperature,
    })
    setShowForm(true)
    setError('')
  }

  const startCreate = () => {
    setEditing(null)
    setForm({
      name: '',
      avatar: '🐹',
      personality: '',
      system_prompt: '',
      llm_config_id: null,
      temperature: 0.7,
    })
    setShowForm(true)
    setError('')
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const data = {
        ...form,
        system_prompt: form.system_prompt || null,
        is_active: false,
      }
      if (editing) {
        await updateAgentConfig(editing.id, data)
      } else {
        await createAgentConfig(data)
      }
      setShowForm(false)
      setEditing(null)
      onRefresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleActivate = async (id: number) => {
    try {
      await activateAgentConfig(id)
      onRefresh()
      // 通知父组件更新
      const active = await getActiveAgent()
      if (active && onAgentChange) {
        onAgentChange(active)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此 Agent 人设？')) return
    try {
      await deleteAgentConfig(id)
      onRefresh()
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="p-6 space-y-4">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          配置 Agent 的名字、头像、性格和人设
        </p>
        {!showForm && (
          <button
            onClick={startCreate}
            className="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm rounded-lg font-medium transition-colors"
          >
            + 添加人设
          </button>
        )}
      </div>

      {/* 表单 */}
      {showForm && (
        <div className="bg-gray-50 rounded-xl p-5 space-y-4 border border-gray-200">
          <h3 className="font-semibold text-gray-700 text-sm">
            {editing ? '编辑人设' : '新增人设'}
          </h3>

          {/* 名字 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Agent 名字</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：仓鼠管家"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none"
            />
          </div>

          {/* 头像选择 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">头像</label>
            <div className="flex gap-2 flex-wrap">
              {AVATAR_OPTIONS.map((emoji) => (
                <button
                  key={emoji}
                  onClick={() => setForm({ ...form, avatar: emoji })}
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-xl transition-all ${
                    form.avatar === emoji
                      ? 'bg-orange-200 ring-2 ring-orange-400 scale-110'
                      : 'bg-gray-100 hover:bg-gray-200'
                  }`}
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>

          {/* 性格描述 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">性格描述</label>
            <textarea
              value={form.personality}
              onChange={(e) => setForm({ ...form, personality: e.target.value })}
              placeholder="如：友好、简洁实用、偶尔幽默、像精明的家庭管家"
              rows={2}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none resize-none"
            />
            <p className="text-xs text-gray-400 mt-1">描述 Agent 的说话风格和性格特征</p>
          </div>

          {/* 系统提示词 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">
              自定义系统提示词（可选）
            </label>
            <textarea
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              placeholder="留空则自动从名字和性格生成。也可填写完整的系统提示词来自定义 Agent 行为。"
              rows={4}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none resize-none"
            />
          </div>

          {/* 关联 LLM 配置 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">
              关联模型（可选，留空则使用默认激活模型）
            </label>
            <select
              value={form.llm_config_id ?? ''}
              onChange={(e) => setForm({ ...form, llm_config_id: e.target.value ? Number(e.target.value) : null })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-300 focus:outline-none bg-white"
            >
              <option value="">使用默认激活模型</option>
              {llmConfigs.map((llm) => (
                <option key={llm.id} value={llm.id}>
                  {llm.name} ({llm.model_name})
                  {llm.is_active ? ' [已激活]' : ''}
                </option>
              ))}
            </select>
          </div>

          {/* 温度 */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">
              对话温度 ({form.temperature}) — 越高越有创意，越低越严谨
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={form.temperature}
              onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
              className="w-full accent-orange-500"
            />
          </div>

          {error && (
            <div className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</div>
          )}

          {/* 表单操作按钮 */}
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setEditing(null); setError('') }}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !form.name}
              className="px-4 py-2 text-sm bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      {/* 配置列表 */}
      <div className="space-y-2">
        {configs.length === 0 && !showForm ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-4xl mb-2">🐹</div>
            <p className="text-sm">还没有配置 Agent 人设，点击「添加人设」开始</p>
          </div>
        ) : (
          configs.map((config) => (
            <div
              key={config.id}
              className={`flex items-center justify-between p-3 rounded-xl border transition-colors ${
                config.is_active
                  ? 'border-orange-300 bg-orange-50'
                  : 'border-gray-200 bg-white hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-3 flex-1">
                <span className="text-2xl">{config.avatar}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{config.name}</span>
                    {config.is_active && (
                      <span className="text-xs px-2 py-0.5 bg-orange-500 text-white rounded-full">
                        已激活
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-1">
                    {config.personality || '无性格描述'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {!config.is_active && (
                  <button
                    onClick={() => handleActivate(config.id)}
                    className="px-3 py-1.5 text-xs text-orange-600 hover:bg-orange-100 rounded-lg transition-colors"
                  >
                    激活
                  </button>
                )}
                <button
                  onClick={() => startEdit(config)}
                  className="px-3 py-1.5 text-xs text-blue-600 hover:bg-blue-100 rounded-lg transition-colors"
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(config.id)}
                  className="px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
