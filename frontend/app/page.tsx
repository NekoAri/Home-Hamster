'use client'

import { useState } from 'react'
import Chat from '@/components/Chat'
import Dashboard from '@/components/Dashboard'
import Settings from '@/components/Settings'
import { getActiveAgent, type AgentConfig } from '@/lib/api'

type Mode = 'agent' | 'normal'

/**
 * HomeHamster 主页面
 *
 * 核心特性：双模式切换
 * - Agent 模式：通过对话与 AI 助手交互，支持自然语言记账、查库存等
 * - 普通模式：直接通过表格/表单操作账目、物品、类别数据，无需对话
 *
 * 模式状态保存在 localStorage 中，刷新后保持上次选择
 */
export default function Home() {
  // 初始化模式：优先读 localStorage，默认 Agent 模式
  const [mode, setMode] = useState<Mode>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('hh-mode')
      return saved === 'normal' ? 'normal' : 'agent'
    }
    return 'agent'
  })

  // 设置弹窗
  const [showSettings, setShowSettings] = useState(false)
  // Agent 人设信息
  const [agentInfo, setAgentInfo] = useState<{ name: string; avatar: string }>({
    name: 'HomeHamster',
    avatar: '🐹',
  })

  // 切换模式
  const handleModeSwitch = (newMode: Mode) => {
    setMode(newMode)
    if (typeof window !== 'undefined') {
      localStorage.setItem('hh-mode', newMode)
    }
  }

  // Agent 人设变更回调
  const handleAgentChange = (agent: AgentConfig) => {
    setAgentInfo({ name: agent.name, avatar: agent.avatar })
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-orange-50 to-amber-50">
      {/* ===== 顶部导航栏 ===== */}
      <header className="flex items-center justify-between px-4 sm:px-6 py-3 bg-white/80 backdrop-blur-md border-b border-orange-100 shadow-sm">
        {/* 左侧：Logo + 名称 */}
        <div className="flex items-center gap-2">
          <span className="text-2xl">{agentInfo.avatar}</span>
          <span className="text-lg font-bold text-gray-800 hidden sm:inline">
            {agentInfo.name}
          </span>
        </div>

        {/* 中间：模式切换器 */}
        <div className="flex items-center bg-gray-100 rounded-full p-1">
          <button
            onClick={() => handleModeSwitch('agent')}
            className={`flex items-center gap-1.5 px-3 sm:px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              mode === 'agent'
                ? 'bg-white text-orange-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span>Agent 对话</span>
          </button>
          <button
            onClick={() => handleModeSwitch('normal')}
            className={`flex items-center gap-1.5 px-3 sm:px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              mode === 'normal'
                ? 'bg-white text-orange-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            <span>数据管理</span>
          </button>
        </div>

        {/* 右侧：设置按钮 */}
        <button
          onClick={() => setShowSettings(true)}
          className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 transition-colors"
          title="设置"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </header>

      {/* ===== 主内容区 ===== */}
      <div className="flex-1 overflow-hidden">
        {mode === 'agent' ? (
          <Chat embedded />
        ) : (
          <Dashboard />
        )}
      </div>

      {/* ===== 设置弹窗 ===== */}
      {showSettings && (
        <Settings
          onClose={() => setShowSettings(false)}
          onAgentChange={handleAgentChange}
        />
      )}
    </div>
  )
}
