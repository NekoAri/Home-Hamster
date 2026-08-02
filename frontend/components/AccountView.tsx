'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  listAccounts, countAccounts, createAccount, updateAccount, deleteAccount,
  type Account, type AccountQueryParams,
} from '@/lib/api'

const PAGE_SIZE = 20

/**
 * 账目管理视图
 *
 * 功能：
 * - 表格展示账目记录（日期、分类、类型、金额、备注）
 * - 按分类、类型、日期范围筛选
 * - 分页
 * - 新增/编辑/删除账目
 */
export default function AccountView() {
  // 数据
  const [accounts, setAccounts] = useState<Account[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // 筛选条件
  const [filters, setFilters] = useState<AccountQueryParams>({
    limit: PAGE_SIZE,
    offset: 0,
  })
  const [page, setPage] = useState(0)

  // 弹窗状态
  const [editing, setEditing] = useState<Account | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Account | null>(null)

  // 加载数据
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = { ...filters, offset: page * PAGE_SIZE, limit: PAGE_SIZE }
      const [data, count] = await Promise.all([
        listAccounts(params),
        countAccounts(params),
      ])
      setAccounts(data)
      setTotal(count.total)
    } catch (err) {
      console.error('加载账目失败:', err)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => {
    loadData()
  }, [loadData])

  // 筛选变化时重置页码
  const handleFilterChange = (key: keyof AccountQueryParams, value: string) => {
    setPage(0)
    setFilters((prev) => ({ ...prev, [key]: value || undefined }))
  }

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1

  return (
    <div className="space-y-4">
      {/* ===== 筛选栏 ===== */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* 类型筛选 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">类型</label>
            <select
              value={filters.type || ''}
              onChange={(e) => handleFilterChange('type', e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            >
              <option value="">全部</option>
              <option value="expense">支出</option>
              <option value="income">收入</option>
            </select>
          </div>

          {/* 分类筛选 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">分类</label>
            <input
              type="text"
              value={filters.category || ''}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              placeholder="如：餐饮"
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 w-32"
            />
          </div>

          {/* 开始日期 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">开始日期</label>
            <input
              type="date"
              value={filters.start_date?.split('T')[0] || ''}
              onChange={(e) => handleFilterChange('start_date', e.target.value ? `${e.target.value}T00:00:00` : '')}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 结束日期 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">结束日期</label>
            <input
              type="date"
              value={filters.end_date?.split('T')[0] || ''}
              onChange={(e) => handleFilterChange('end_date', e.target.value ? `${e.target.value}T23:59:59` : '')}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 重置按钮 */}
          <button
            onClick={() => { setPage(0); setFilters({ limit: PAGE_SIZE, offset: 0 }) }}
            className="px-3 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm transition-colors"
          >
            重置
          </button>

          {/* 新增按钮 */}
          <button
            onClick={() => { setEditing(null); setShowForm(true) }}
            className="ml-auto px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            新增账目
          </button>
        </div>
      </div>

      {/* ===== 数据表格 ===== */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex gap-1">
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        ) : accounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <img src="/hamsters/money.png" alt="" className="w-20 h-20 rounded-2xl object-cover mb-3 opacity-80" />
            <p className="text-sm">暂无账目记录</p>
          </div>
        ) : (
          <>
            {/* 桌面端表格 */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-xs">
                    <th className="px-4 py-3 text-left font-medium">日期</th>
                    <th className="px-4 py-3 text-left font-medium">分类</th>
                    <th className="px-4 py-3 text-left font-medium">类型</th>
                    <th className="px-4 py-3 text-right font-medium">金额</th>
                    <th className="px-4 py-3 text-left font-medium">备注</th>
                    <th className="px-4 py-3 text-center font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {accounts.map((item) => (
                    <tr key={item.id} className="hover:bg-orange-50/50 transition-colors">
                      <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                        {new Date(item.occurred_at).toLocaleDateString('zh-CN')}
                      </td>
                      <td className="px-4 py-3 text-gray-700">{item.category}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${
                          item.type === 'expense'
                            ? 'bg-red-100 text-red-600'
                            : 'bg-green-100 text-green-600'
                        }`}>
                          {item.type === 'expense' ? '支出' : '收入'}
                        </span>
                      </td>
                      <td className={`px-4 py-3 text-right font-medium whitespace-nowrap ${
                        item.type === 'expense' ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {item.type === 'expense' ? '-' : '+'}¥{Math.abs(item.amount).toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate">
                        {item.note || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => { setEditing(item); setShowForm(true) }}
                            className="text-gray-400 hover:text-orange-600 transition-colors"
                            title="编辑"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => setDeleteTarget(item)}
                            className="text-gray-400 hover:text-red-500 transition-colors"
                            title="删除"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 移动端卡片列表 */}
            <div className="md:hidden divide-y divide-gray-100">
              {accounts.map((item) => (
                <div key={item.id} className="p-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-gray-700 font-medium">{item.category}</span>
                    <span className={`font-bold ${
                      item.type === 'expense' ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {item.type === 'expense' ? '-' : '+'}¥{Math.abs(item.amount).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-400">
                    <span>{new Date(item.occurred_at).toLocaleDateString('zh-CN')}</span>
                    <span className={`px-2 py-0.5 rounded-full ${
                      item.type === 'expense' ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-500'
                    }`}>
                      {item.type === 'expense' ? '支出' : '收入'}
                    </span>
                  </div>
                  {item.note && <p className="text-xs text-gray-500 mt-1 truncate">{item.note}</p>}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => { setEditing(item); setShowForm(true) }}
                      className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600"
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => setDeleteTarget(item)}
                      className="text-xs px-2 py-1 rounded bg-red-50 text-red-500"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* 分页 */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <span className="text-xs text-gray-500">
                共 {total} 条，第 {page + 1}/{totalPages} 页
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-gray-600 text-sm transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-gray-600 text-sm transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ===== 新增/编辑弹窗 ===== */}
      {showForm && (
        <AccountForm
          account={editing}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadData() }}
        />
      )}

      {/* ===== 删除确认弹窗 ===== */}
      {deleteTarget && (
        <DeleteConfirm
          title="删除账目"
          message={`确认删除「${deleteTarget.category} ¥${Math.abs(deleteTarget.amount).toFixed(2)}」这条记录吗？`}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={async () => {
            try {
              await deleteAccount(deleteTarget.id)
              setDeleteTarget(null)
              loadData()
            } catch (err) {
              alert('删除失败: ' + (err as Error).message)
            }
          }}
        />
      )}
    </div>
  )
}

// ============================================================
// 账目表单弹窗
// ============================================================

function AccountForm({
  account,
  onClose,
  onSaved,
}: {
  account: Account | null
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = !!account
  const [form, setForm] = useState({
    amount: account ? Math.abs(account.amount).toString() : '',
    category: account?.category || '',
    type: account?.type || 'expense',
    occurred_at: account ? account.occurred_at.slice(0, 10) : new Date().toISOString().slice(0, 10),
    note: account?.note || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const amount = parseFloat(form.amount)
      if (isNaN(amount) || amount <= 0) {
        throw new Error('金额必须大于 0')
      }
      const data = {
        amount: form.type === 'expense' ? -amount : amount,
        category: form.category.trim(),
        type: form.type,
        occurred_at: `${form.occurred_at}T${new Date().toTimeString().slice(0, 8)}`,
        note: form.note.trim() || undefined,
      }
      if (isEdit && account) {
        await updateAccount(account.id, data)
      } else {
        await createAccount(data)
      }
      onSaved()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-gray-800 mb-4">
          {isEdit ? '编辑账目' : '新增账目'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 类型切换 */}
          <div className="flex gap-2">
            {(['expense', 'income'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setForm({ ...form, type: t })}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                  form.type === t
                    ? t === 'expense'
                      ? 'bg-red-500 text-white'
                      : 'bg-green-500 text-white'
                    : 'bg-gray-100 text-gray-500'
                }`}
              >
                {t === 'expense' ? '💸 支出' : '💰 收入'}
              </button>
            ))}
          </div>

          {/* 金额 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">金额 *</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">¥</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                required
                className="w-full pl-8 pr-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                placeholder="0.00"
              />
            </div>
          </div>

          {/* 分类 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">分类 *</label>
            <input
              type="text"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              required
              list="account-categories"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              placeholder="如：餐饮、交通、工资"
            />
            <datalist id="account-categories">
              <option value="餐饮" />
              <option value="交通" />
              <option value="购物" />
              <option value="娱乐" />
              <option value="生活" />
              <option value="医疗" />
              <option value="工资" />
              <option value="其他收入" />
            </datalist>
          </div>

          {/* 日期 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">日期</label>
            <input
              type="date"
              value={form.occurred_at}
              onChange={(e) => setForm({ ...form, occurred_at: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 备注 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">备注</label>
            <textarea
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
              placeholder="可选..."
            />
          </div>

          {error && (
            <p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm font-medium transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {saving ? '保存中...' : isEdit ? '更新' : '添加'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ============================================================
// 删除确认弹窗（通用组件，可被其他视图复用）
// ============================================================

export function DeleteConfirm({
  title,
  message,
  onCancel,
  onConfirm,
  confirming = false,
}: {
  title: string
  message: string
  onCancel: () => void
  onConfirm: () => void
  confirming?: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-500">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h3 className="font-bold text-gray-800">{title}</h3>
            <p className="text-sm text-gray-500 mt-1">{message}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm font-medium transition-colors"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={confirming}
            className="flex-1 py-2 rounded-lg bg-red-500 hover:bg-red-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {confirming ? '删除中...' : '确认删除'}
          </button>
        </div>
      </div>
    </div>
  )
}
