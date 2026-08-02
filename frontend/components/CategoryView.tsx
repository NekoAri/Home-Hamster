'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  listCategories, createCategory, updateCategory, deleteCategory,
  type Category,
} from '@/lib/api'
import { DeleteConfirm } from './AccountView'

/**
 * 物品类别管理视图
 *
 * 功能：
 * - 卡片/列表展示所有类别
 * - 新增/编辑/删除类别
 * - 显示类别编号 (code)
 */
export default function CategoryView() {
  // 数据
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(false)

  // 弹窗状态
  const [editing, setEditing] = useState<Category | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null)

  // 加载数据
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listCategories()
      setCategories(data)
    } catch (err) {
      console.error('加载类别失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="space-y-4">
      {/* ===== 工具栏 ===== */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          共 {categories.length} 个类别
        </p>
        <button
          onClick={() => { setEditing(null); setShowForm(true) }}
          className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新增类别
        </button>
      </div>

      {/* ===== 类别列表 ===== */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex gap-1">
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="inline-block w-2.5 h-2.5 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        ) : categories.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <img src="/hamsters/logo.png" alt="" className="w-20 h-20 rounded-2xl object-cover mb-3 opacity-80" />
            <p className="text-sm">暂无类别，点击右上角新增</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
            {categories.map((cat) => (
              <div
                key={cat.id}
                className="group border border-gray-100 rounded-xl p-4 hover:border-orange-200 hover:shadow-md transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center text-lg">
                      🏷️
                    </div>
                    <div>
                      <p className="font-medium text-gray-800">{cat.name}</p>
                      <p className="text-xs text-gray-400">{cat.code}</p>
                    </div>
                  </div>
                  {/* 操作按钮 */}
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => { setEditing(cat); setShowForm(true) }}
                      className="w-7 h-7 rounded-lg bg-gray-100 hover:bg-orange-100 text-gray-400 hover:text-orange-600 flex items-center justify-center transition-colors"
                      title="编辑"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setDeleteTarget(cat)}
                      className="w-7 h-7 rounded-lg bg-gray-100 hover:bg-red-100 text-gray-400 hover:text-red-500 flex items-center justify-center transition-colors"
                      title="删除"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
                      </svg>
                    </button>
                  </div>
                </div>
                {cat.description && (
                  <p className="text-xs text-gray-400 mt-2">{cat.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ===== 新增/编辑弹窗 ===== */}
      {showForm && (
        <CategoryForm
          category={editing}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadData() }}
        />
      )}

      {/* ===== 删除确认 ===== */}
      {deleteTarget && (
        <DeleteConfirm
          title="删除类别"
          message={`确认删除类别「${deleteTarget.name}」(${deleteTarget.code})吗？关联的物品将变为未分类。`}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={async () => {
            try {
              await deleteCategory(deleteTarget.id)
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
// 类别表单弹窗
// ============================================================

function CategoryForm({
  category,
  onClose,
  onSaved,
}: {
  category: Category | null
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = !!category
  const [form, setForm] = useState({
    name: category?.name || '',
    code: category?.code || '',
    description: category?.description || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const data = {
        name: form.name.trim(),
        code: form.code.trim(),
        description: form.description.trim() || undefined,
      }
      if (isEdit && category) {
        await updateCategory(category.id, data)
      } else {
        await createCategory(data)
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
        className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-gray-800 mb-4">
          {isEdit ? '编辑类别' : '新增类别'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 名称 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">类别名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              placeholder="如：食品、日用品"
            />
          </div>

          {/* 编号 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">类别编号 *</label>
            <input
              type="text"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              required
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              placeholder="如：FOOD、DAILY"
            />
          </div>

          {/* 描述 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
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
