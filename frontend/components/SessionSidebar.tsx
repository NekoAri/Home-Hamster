'use client'

import { useState } from 'react'
import type { ChatSession } from '@/lib/api'

interface SessionSidebarProps {
  sessions: ChatSession[]
  currentSessionId: string | null
  visible: boolean
  loading: boolean
  onNewSession: () => void
  onSwitchSession: (sessionId: string) => void
  onDeleteSession: (sessionId: string) => void
  onClose: () => void
}

/**
 * 会话列表侧边栏
 *
 * 显示用户的对话历史列表，支持：
 * - 新建对话
 * - 切换到历史对话
 * - 删除对话
 * - 显示每条对话的标题、最后消息预览和时间
 */
export default function SessionSidebar({
  sessions,
  currentSessionId,
  visible,
  loading,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  onClose,
}: SessionSidebarProps) {

  /** 格式化时间显示 */
  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return ''
    const date = new Date(timeStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    if (hours < 24) return `${hours}小时前`
    if (days < 7) return `${days}天前`
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  return (
    <>
      {/* 遮罩层（移动端） */}
      {visible && (
        <div
          className="fixed inset-0 bg-black/20 z-30 md:hidden"
          onClick={onClose}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={`
          fixed md:relative left-0 top-0 h-full z-40
          w-72 bg-white border-r border-orange-100 flex flex-col
          transition-transform duration-300 ease-in-out
          ${visible ? 'translate-x-0' : '-translate-x-full md:-translate-x-full md:w-0 md:border-0 md:overflow-hidden'}
        `}
      >
        {/* 侧边栏头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-orange-100">
          <div className="flex items-center gap-2">
            <img src="/hamsters/logo.png" alt="Hamster" className="w-7 h-7 rounded-full object-cover" />
            <span className="text-sm font-semibold text-gray-700">对话历史</span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 新建对话按钮 */}
        <div className="p-3">
          <button
            onClick={onNewSession}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            新对话
          </button>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto chat-scrollbar px-2 pb-2">
          {loading && sessions.length === 0 && (
            <div className="flex justify-center py-8">
              <div className="flex gap-1">
                <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}

          {!loading && sessions.length === 0 && (
            <div className="flex flex-col items-center py-8 text-gray-400">
              <img src="/hamsters/sleep.png" alt="Sleep" className="w-16 h-16 rounded-full object-cover mb-2 opacity-60" />
              <p className="text-xs">还没有对话记录</p>
            </div>
          )}

          {sessions.map((session) => (
            <div
              key={session.session_id}
              onClick={() => onSwitchSession(session.session_id)}
              className={`
                group relative px-3 py-2.5 rounded-lg cursor-pointer mb-1 transition-colors
                ${session.session_id === currentSessionId
                  ? 'bg-orange-50 border border-orange-200'
                  : 'hover:bg-gray-50'
                }
              `}
            >
              {/* 标题 */}
              <p className={`text-sm font-medium truncate ${
                session.session_id === currentSessionId ? 'text-orange-700' : 'text-gray-700'
              }`}>
                {session.title || '新对话'}
              </p>

              {/* 最后消息预览 */}
              {session.last_message && (
                <p className="text-xs text-gray-400 truncate mt-0.5">
                  {session.last_message}
                </p>
              )}

              {/* 时间 + 删除按钮 */}
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-gray-300">
                  {formatTime(session.last_message_time || session.updated_at)}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm('确定删除这个对话吗？')) {
                      onDeleteSession(session.session_id)
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 w-6 h-6 rounded flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                  title="删除对话"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  )
}
