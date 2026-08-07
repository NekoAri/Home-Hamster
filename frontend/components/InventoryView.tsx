'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  listInventory, countInventory, createInventory, updateInventory, deleteInventory,
  listCategories,
  type InventoryItem, type InventoryQueryParams, type Category,
} from '@/lib/api'
import { DeleteConfirm } from './AccountView'

const PAGE_SIZE = 20

/**
 * 物品仓储管理视图
 *
 * 功能：
 * - 表格展示物品列表（名称、条码、类别、数量、位置、过期时间）
 * - 按名称、类别、位置、条码筛选
 * - 分页
 * - 新增/编辑/删除物品（含 JSONB 自定义属性编辑）
 */
export default function InventoryView() {
  // 数据
  const [items, setItems] = useState<InventoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(false)

  // 筛选条件
  const [filters, setFilters] = useState<InventoryQueryParams>({
    limit: PAGE_SIZE,
    offset: 0,
  })
  const [page, setPage] = useState(0)

  // 弹窗状态
  const [editing, setEditing] = useState<InventoryItem | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<InventoryItem | null>(null)

  // 加载类别列表（用于下拉选择）
  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => {})
  }, [])

  // 加载物品数据
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = { ...filters, offset: page * PAGE_SIZE, limit: PAGE_SIZE }
      const [data, count] = await Promise.all([
        listInventory(params),
        countInventory(params),
      ])
      setItems(data)
      setTotal(count.total)
    } catch (err) {
      console.error('加载物品失败:', err)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleFilterChange = (key: keyof InventoryQueryParams, value: string) => {
    setPage(0)
    const val = key === 'category_id' ? (value ? parseInt(value) : undefined) : value
    setFilters((prev) => ({ ...prev, [key]: val || undefined }))
  }

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1

  // 获取类别名称
  const getCategoryName = (categoryId: number | null, categoryName?: string | null) => {
    if (categoryName) return categoryName
    if (!categoryId) return '未分类'
    return categories.find((c) => c.id === categoryId)?.name || '未分类'
  }

  // 固定时间戳，避免 SSR/CSR 渲染时 Date.now() 不一致导致 hydration error
  const nowTs = useMemo(() => Date.now(), [])

  // 检查是否临期（30天内）
  const isExpiringSoon = (dateStr: string | null) => {
    if (!dateStr) return false
    const diff = new Date(dateStr).getTime() - nowTs
    return diff < 30 * 24 * 60 * 60 * 1000
  }
  const isExpired = (dateStr: string | null) => {
    if (!dateStr) return false
    return new Date(dateStr).getTime() < nowTs
  }

  return (
    <div className="space-y-4">
      {/* ===== 筛选栏 ===== */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* 名称搜索 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">物品名称</label>
            <input
              type="text"
              value={filters.name || ''}
              onChange={(e) => handleFilterChange('name', e.target.value)}
              placeholder="搜索..."
              className="w-32 h-9 px-3 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 类别筛选 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">类别</label>
            <select
              value={filters.category_id || ''}
              onChange={(e) => handleFilterChange('category_id', e.target.value)}
              className="w-32 h-9 px-3 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            >
              <option value="">全部</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* 位置搜索 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">位置</label>
            <input
              type="text"
              value={filters.location || ''}
              onChange={(e) => handleFilterChange('location', e.target.value)}
              placeholder="搜索..."
              className="w-32 h-9 px-3 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 条码搜索 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">条码</label>
            <input
              type="text"
              value={filters.barcode || ''}
              onChange={(e) => handleFilterChange('barcode', e.target.value)}
              placeholder="搜索..."
              className="w-32 h-9 px-3 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </div>

          {/* 重置 */}
          <button
            onClick={() => { setPage(0); setFilters({ limit: PAGE_SIZE, offset: 0 }) }}
            className="h-9 px-3 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm transition-colors"
          >
            重置
          </button>

          {/* 新增 */}
          <button
            onClick={() => { setEditing(null); setShowForm(true) }}
            className="ml-auto h-9 px-4 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            新增物品
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
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <img src="/hamsters/inventory.png" alt="" className="w-20 h-20 rounded-2xl object-cover mb-3 opacity-80" />
            <p className="text-sm">暂无物品记录</p>
          </div>
        ) : (
          <>
            {/* 桌面端表格 */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-xs">
                    <th className="px-4 py-3 text-left font-medium">名称</th>
                    <th className="px-4 py-3 text-left font-medium">类别</th>
                    <th className="px-4 py-3 text-right font-medium">数量</th>
                    <th className="px-4 py-3 text-left font-medium">位置</th>
                    <th className="px-4 py-3 text-left font-medium">过期时间</th>
                    <th className="px-4 py-3 text-center font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-orange-50/50 transition-colors">
                      <td className="px-4 py-3 text-gray-700 font-medium">
                        {item.name}
                        {item.barcode && (
                          <span className="block text-xs text-gray-400">{item.barcode}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {getCategoryName(item.category_id, (item as any).category_name)}
                      </td>
                      <td className={`px-4 py-3 text-right font-medium ${
                        item.quantity <= 5 ? 'text-red-600' : 'text-gray-700'
                      }`}>
                        {item.quantity} {item.unit}
                        {item.quantity <= 5 && <span className="text-xs"> ⚠️</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{item.location || '-'}</td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        {item.expiry_date ? (
                          <span className={isExpired(item.expiry_date) ? 'text-red-600 font-medium' :
                            isExpiringSoon(item.expiry_date) ? 'text-orange-500' : ''}>
                            {new Date(item.expiry_date).toLocaleDateString('zh-CN')}
                            {isExpired(item.expiry_date) && ' ❌'}
                            {isExpiringSoon(item.expiry_date) && !isExpired(item.expiry_date) && ' ⏰'}
                          </span>
                        ) : '-'}
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

            {/* 移动端卡片 */}
            <div className="md:hidden divide-y divide-gray-100">
              {items.map((item) => (
                <div key={item.id} className="p-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-gray-700 font-medium">{item.name}</span>
                    <span className={`font-bold ${item.quantity <= 5 ? 'text-red-600' : 'text-gray-700'}`}>
                      {item.quantity} {item.unit}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>{getCategoryName(item.category_id, (item as any).category_name)}</span>
                    {item.location && <span>· {item.location}</span>}
                  </div>
                  {item.expiry_date && (
                    <div className={`text-xs mt-1 ${
                      isExpired(item.expiry_date) ? 'text-red-500' :
                      isExpiringSoon(item.expiry_date) ? 'text-orange-500' : 'text-gray-400'
                    }`}>
                      {isExpired(item.expiry_date) ? '已过期' : '过期'}: {new Date(item.expiry_date).toLocaleDateString('zh-CN')}
                    </div>
                  )}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => { setEditing(item); setShowForm(true) }}
                      className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600"
                    >编辑</button>
                    <button
                      onClick={() => setDeleteTarget(item)}
                      className="text-xs px-2 py-1 rounded bg-red-50 text-red-500"
                    >删除</button>
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
                >上一页</button>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-gray-600 text-sm transition-colors"
                >下一页</button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ===== 新增/编辑弹窗 ===== */}
      {showForm && (
        <InventoryForm
          item={editing}
          categories={categories}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadData() }}
        />
      )}

      {/* ===== 删除确认 ===== */}
      {deleteTarget && (
        <DeleteConfirm
          title="删除物品"
          message={`确认删除「${deleteTarget.name}」(${deleteTarget.quantity} ${deleteTarget.unit})吗？`}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={async () => {
            try {
              await deleteInventory(deleteTarget.id)
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
// 物品表单弹窗
// ============================================================

function InventoryForm({
  item,
  categories,
  onClose,
  onSaved,
}: {
  item: InventoryItem | null
  categories: Category[]
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = !!item
  const [form, setForm] = useState({
    name: item?.name || '',
    barcode: item?.barcode || '',
    category_id: item?.category_id?.toString() || '',
    quantity: item?.quantity?.toString() || '1',
    unit: item?.unit || '个',
    location: item?.location || '',
    expiry_date: item?.expiry_date?.slice(0, 10) || '',
    custom_attrs: item?.custom_attrs ? JSON.stringify(item.custom_attrs, null, 2) : '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const quantity = parseInt(form.quantity)
      if (isNaN(quantity) || quantity < 0) throw new Error('数量必须为非负整数')

      // 解析自定义属性 JSON
      let customAttrs: Record<string, any> | undefined
      if (form.custom_attrs.trim()) {
        try {
          customAttrs = JSON.parse(form.custom_attrs)
        } catch {
          throw new Error('自定义属性 JSON 格式错误')
        }
      }

      const data = {
        name: form.name.trim(),
        barcode: form.barcode.trim() || undefined,
        category_id: form.category_id ? parseInt(form.category_id) : undefined,
        quantity,
        unit: form.unit.trim() || '个',
        location: form.location.trim() || undefined,
        expiry_date: form.expiry_date || undefined,
        custom_attrs: customAttrs,
      }

      if (isEdit && item) {
        await updateInventory(item.id, data)
      } else {
        await createInventory(data)
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
        className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-gray-800 mb-4">
          {isEdit ? '编辑物品' : '新增物品'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 名称 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">物品名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              placeholder="如：可口可乐"
            />
          </div>

          {/* 条码 + 类别 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">条码</label>
              <input
                type="text"
                value={form.barcode}
                onChange={(e) => setForm({ ...form, barcode: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                placeholder="可选"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">类别</label>
              <select
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                <option value="">未分类</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 数量 + 单位 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">数量 *</label>
              <input
                type="number"
                min="0"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                required
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">单位</label>
              <input
                type="text"
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                placeholder="个/瓶/箱..."
              />
            </div>
          </div>

          {/* 位置 + 过期时间 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">存放位置</label>
              <input
                type="text"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                placeholder="如：冰箱、储藏室"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">过期时间</label>
              <input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
          </div>

          {/* 自定义属性 JSON */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">自定义属性 (JSON)</label>
            <textarea
              value={form.custom_attrs}
              onChange={(e) => setForm({ ...form, custom_attrs: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
              placeholder='{"品牌": "可口可乐", "规格": "330ml"}'
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
            >取消</button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >{saving ? '保存中...' : isEdit ? '更新' : '添加'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
