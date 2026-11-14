'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  listMemories,
  updateMemory,
  deleteMemory,
  type AgentMemory,
} from '@/lib/api'

/**
 * 记忆列表视图（P3）
 *
 * 「它记住了什么」完全可见：支持纠正和删除。
 * 记忆不可见 = 不可信，所以全部列在这里，没有任何隐藏记忆。
 */
export default function MemoriesView() {
  const [memories, setMemories] = useState<AgentMemory[]>([])
  const [filter, setFilter] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [toast, setToast] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setMemories(await listMemories(filter))
    } catch (err) {
      console.error('加载记忆失败:', err)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    load()
  }, [load])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  const handleSave = async (id: number) => {
    const text = editText.trim()
    if (text.length < 2) {
      showToast('内容太短')
      return
    }
    try {
      await updateMemory(id, text)
      setEditingId(null)
      showToast('已纠正')
      await load()
    } catch (err) {
      console.error('纠正失败:', err)
      showToast('保存失败，请稍后再试')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMemory(id)
      setMemories((prev) => prev.filter((m) => m.id !== id))
      showToast('已删除，我不会再记着这件事')
    } catch (err) {
      console.error('删除失败:', err)
      showToast('删除失败，请稍后再试')
    }
  }

  const typeLabels: Record<string, string> = {
    preference: '偏好',
    fact: '事实',
    habit: '习惯',
  }
  const typeColors: Record<string, string> = {
    preference: 'bg-purple-100 text-purple-700',
    fact: 'bg-blue-100 text-blue-700',
    habit: 'bg-green-100 text-green-700',
  }

  const filters: { key: string; label: string }[] = [
    { key: '', label: '全部' },
    { key: 'preference', label: '偏好' },
    { key: 'fact', label: '事实' },
    { key: 'habit', label: '习惯' },
  ]

  return (
    <div className="space-y-5">
      {/* ===== 头部说明 + 筛选 ===== */}
      <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
        <h2 className="flex items-center gap-2 text-lg font-bold text-gray-800 mb-1">
          <span>🧠</span>
          <span>管家记住了什么</span>
        </h2>
        <p className="text-xs text-gray-400 mb-4">
          这些是我在对话中沉淀的长期记忆，全部公开在这里。哪条不对就纠正，不想要就删掉。
        </p>
        <div className="flex items-center gap-2">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                filter === f.key
                  ? 'bg-orange-500 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-orange-50 hover:text-orange-600'
              }`}
            >
              {f.label}
            </button>
          ))}
          <span className="ml-auto text-xs text-gray-400">共 {memories.length} 条</span>
        </div>
      </section>

      {/* ===== 记忆列表 ===== */}
      <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
        {loading ? (
          <div className="py-10 text-center text-gray-400 text-sm">加载中…</div>
        ) : memories.length === 0 ? (
          <div className="py-10 text-center text-gray-400 text-sm">
            还没有记住任何东西。多和我聊聊天，值得记住的事我会悄悄记下来。
          </div>
        ) : (
          <ul className="divide-y divide-orange-50">
            {memories.map((m) => (
              <li key={m.id} className="py-3.5 flex items-start gap-3">
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${typeColors[m.memory_type] || 'bg-gray-100 text-gray-600'}`}>
                  {typeLabels[m.memory_type] || m.memory_type}
                </span>
                <div className="flex-1 min-w-0">
                  {editingId === m.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSave(m.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        autoFocus
                        className="flex-1 px-2.5 py-1.5 rounded-lg border border-orange-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-200"
                      />
                      <button
                        onClick={() => handleSave(m.id)}
                        className="px-2.5 py-1 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium"
                      >
                        保存
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-medium"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-700 leading-relaxed break-words">{m.content}</p>
                  )}
                  <p className="text-xs text-gray-300 mt-1">记录于 {m.created_at.slice(0, 10)}</p>
                </div>
                {editingId !== m.id && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => {
                        setEditingId(m.id)
                        setEditText(m.content)
                      }}
                      className="px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-medium transition-colors"
                    >
                      纠正
                    </button>
                    <button
                      onClick={() => handleDelete(m.id)}
                      className="px-2.5 py-1 rounded-lg bg-red-50 hover:bg-red-100 text-red-500 text-xs font-medium transition-colors"
                    >
                      删除
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ===== Toast ===== */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-gray-800 text-white text-sm shadow-lg z-50">
          {toast}
        </div>
      )}
    </div>
  )
}
