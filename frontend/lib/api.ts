/**
 * HomeHamster 前端 API 辅助函数
 * 封装所有与后端的请求交互
 */

// ---- 类型定义 ----

export interface ProviderPreset {
  label: string
  default_base_url: string
  default_model: string
  needs_api_key: boolean
  description: string
}

export interface LLMConfig {
  id: number
  name: string
  provider: string
  api_key: string
  base_url: string | null
  model_name: string
  embedding_model: string | null
  temperature: number
  max_tokens: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AgentConfig {
  id: number
  name: string
  avatar: string
  personality: string
  system_prompt: string | null
  llm_config_id: number | null
  temperature: number
  is_active: boolean
  created_at: string
  updated_at: string
}

// ---- 对话会话相关类型 ----

export interface ChatSession {
  id: number
  session_id: string
  user_id: string
  title: string
  message_count: number
  summary: string
  last_message: string | null
  last_message_time: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessageRecord {
  id: number
  session_id: string
  role: string  // 'user' | 'assistant' | 'tool'
  content: string
  tool_calls: any[] | null
  tool_call_id: string | null
  token_count: number
  created_at: string
}

export interface SessionMessagesResponse {
  session: ChatSession
  messages: ChatMessageRecord[]
}

// ---- 账目相关类型 ----

export interface Ledger {
  id: number
  name: string
  icon: string
  color: string
  description: string | null
  is_default: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface LedgerWithStats extends Ledger {
  record_count: number
  total_expense: number
  total_income: number
}

export interface Account {
  id: number
  amount: number
  category: string
  type: string  // 'expense' | 'income'
  ledger_id: number
  ledger_name?: string | null
  occurred_at: string
  note: string | null
  created_at: string
  updated_at: string
}

export interface AccountQueryParams {
  limit?: number
  offset?: number
  category?: string
  type?: string
  ledger_id?: number
  start_date?: string
  end_date?: string
}

// ---- 物品仓储相关类型 ----

export interface InventoryItem {
  id: number
  name: string
  barcode: string | null
  category_id: number | null
  category_name?: string | null
  quantity: number
  unit: string
  location: string | null
  expiry_date: string | null
  custom_attrs: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface InventoryQueryParams {
  limit?: number
  offset?: number
  name?: string
  category_id?: number
  location?: string
  barcode?: string
}

// ---- 类别相关类型 ----

export interface Category {
  id: number
  name: string
  code: string
  description: string | null
  created_at: string
  updated_at: string
}

// ---- 统计概览类型 ----

export interface OverviewData {
  total_expense: number
  total_income: number
  net_amount: number
  transaction_count: number
  period: { start: string; end: string }
  category_breakdown: { category: string; total: number; count: number }[]
  daily_trend: { date: string; expense: number; count: number }[]
}

export interface InventoryStats {
  total_items: number
  total_quantity: number
  low_stock_alerts: InventoryItem[]
  expiring_alerts: InventoryItem[]
  expired_items: InventoryItem[]
  location_breakdown: { location: string; items: number; total_quantity: number }[]
  category_breakdown: { category: string; items: number; total_quantity: number }[]
}

// ---- 基础请求函数 ----

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `请求失败: ${response.status}`)
  }
  return response.json()
}

/** 构建 query string 的辅助函数 */
function buildQuery(params: Record<string, any>): string {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value))
    }
  }
  const qs = searchParams.toString()
  return qs ? `?${qs}` : ''
}

// ============================================================
// 供应商预设 & LLM 配置 API
// ============================================================

export async function getProviders(): Promise<Record<string, ProviderPreset>> {
  return apiFetch('/api/configs/providers')
}

export async function listLLMConfigs(): Promise<LLMConfig[]> {
  return apiFetch('/api/configs/llm')
}

export async function createLLMConfig(data: Partial<LLMConfig>): Promise<LLMConfig> {
  return apiFetch('/api/configs/llm', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateLLMConfig(id: number, data: Partial<LLMConfig>): Promise<LLMConfig> {
  return apiFetch(`/api/configs/llm/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteLLMConfig(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/configs/llm/${id}`, { method: 'DELETE' })
}

export async function activateLLMConfig(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/configs/llm/${id}/activate`, { method: 'POST' })
}

// ============================================================
// Agent 人设 API
// ============================================================

export async function listAgentConfigs(): Promise<AgentConfig[]> {
  return apiFetch('/api/configs/agent')
}

export async function getActiveAgent(): Promise<AgentConfig | null> {
  return apiFetch('/api/configs/agent/active')
}

export async function createAgentConfig(data: Partial<AgentConfig>): Promise<AgentConfig> {
  return apiFetch('/api/configs/agent', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAgentConfig(id: number, data: Partial<AgentConfig>): Promise<AgentConfig> {
  return apiFetch(`/api/configs/agent/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteAgentConfig(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/configs/agent/${id}`, { method: 'DELETE' })
}

export async function activateAgentConfig(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/configs/agent/${id}/activate`, { method: 'POST' })
}

// ============================================================
// 账本 CRUD API
// ============================================================

export async function listLedgers(withStats: boolean = false): Promise<LedgerWithStats[]> {
  return apiFetch(`/api/ledgers${buildQuery({ with_stats: withStats })}`)
}

export async function createLedger(data: {
  name: string
  icon?: string
  color?: string
  description?: string
  is_default?: boolean
  sort_order?: number
}): Promise<Ledger> {
  return apiFetch('/api/ledgers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateLedger(id: number, data: Partial<Ledger>): Promise<Ledger> {
  return apiFetch(`/api/ledgers/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteLedger(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/ledgers/${id}`, { method: 'DELETE' })
}

// ============================================================
// 账目 CRUD API
// ============================================================

export async function listAccounts(params: AccountQueryParams = {}): Promise<Account[]> {
  return apiFetch(`/api/accounts${buildQuery(params)}`)
}

export async function countAccounts(params: AccountQueryParams = {}): Promise<{ total: number }> {
  return apiFetch(`/api/summary/accounts/count${buildQuery(params)}`)
}

export async function createAccount(data: {
  amount: number
  category: string
  type?: string
  ledger_id?: number
  occurred_at?: string
  note?: string
}): Promise<Account> {
  return apiFetch('/api/accounts', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAccount(id: number, data: Partial<Account>): Promise<Account> {
  return apiFetch(`/api/accounts/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteAccount(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/accounts/${id}`, { method: 'DELETE' })
}

// ============================================================
// 物品仓储 CRUD API
// ============================================================

export async function listInventory(params: InventoryQueryParams = {}): Promise<InventoryItem[]> {
  return apiFetch(`/api/inventory${buildQuery(params)}`)
}

export async function countInventory(params: InventoryQueryParams = {}): Promise<{ total: number }> {
  return apiFetch(`/api/summary/inventory/count${buildQuery(params)}`)
}

export async function createInventory(data: {
  name: string
  barcode?: string
  category_id?: number
  quantity?: number
  unit?: string
  location?: string
  expiry_date?: string
  custom_attrs?: Record<string, any>
}): Promise<InventoryItem> {
  return apiFetch('/api/inventory', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateInventory(id: number, data: Partial<InventoryItem>): Promise<InventoryItem> {
  return apiFetch(`/api/inventory/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteInventory(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/inventory/${id}`, { method: 'DELETE' })
}

// ============================================================
// 物品类别 CRUD API
// ============================================================

export async function listCategories(): Promise<Category[]> {
  return apiFetch('/api/categories')
}

export async function createCategory(data: {
  name: string
  code: string
  description?: string
}): Promise<Category> {
  return apiFetch('/api/categories', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateCategory(id: number, data: Partial<Category>): Promise<Category> {
  return apiFetch(`/api/categories/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteCategory(id: number): Promise<{ message: string }> {
  return apiFetch(`/api/categories/${id}`, { method: 'DELETE' })
}

// ============================================================
// 统计概览 API
// ============================================================

export async function getOverview(params: {
  start_date?: string
  end_date?: string
} = {}): Promise<OverviewData> {
  return apiFetch(`/api/summary/overview${buildQuery(params)}`)
}

export async function getInventoryStats(): Promise<InventoryStats> {
  return apiFetch('/api/summary/inventory-stats')
}

// ============================================================
// 对话会话管理 API [v3 新增]
// ============================================================

export async function createSession(data: {
  user_id?: string
  title?: string
}): Promise<ChatSession> {
  return apiFetch('/api/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function listSessions(user_id: string = 'default'): Promise<ChatSession[]> {
  return apiFetch(`/api/sessions?user_id=${encodeURIComponent(user_id)}`)
}

export async function getSessionMessages(sessionId: string): Promise<SessionMessagesResponse> {
  return apiFetch(`/api/sessions/${sessionId}/messages`)
}

export async function deleteSession(sessionId: string): Promise<{ message: string }> {
  return apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function updateSessionTitle(sessionId: string, title: string): Promise<ChatSession> {
  return apiFetch(`/api/sessions/${sessionId}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  })
}
