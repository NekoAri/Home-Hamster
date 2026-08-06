'use client'

import { useChat } from 'ai/react'
import { useRef, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import Settings from './Settings'
import SessionSidebar from './SessionSidebar'
import { getActiveAgent, type AgentConfig, createSession, listSessions, getSessionMessages, deleteSession, type ChatSession, type ChatMessageRecord } from '@/lib/api'

interface ChatProps {
  /** 嵌入模式：不渲染自身顶部栏（由外层统一管理导航） */
  embedded?: boolean
}

/**
 * HomeHamster 对话组件（v3 - 服务端历史管理）
 *
 * v3 改进：
 * - 使用 session_id + content 替代全量 messages，前端只发送最新消息
 * - 对话历史由后端管理（滑动窗口 + 自动摘要），避免长对话阻塞
 * - 新增会话列表侧边栏，支持多会话切换
 * - 全局 Agent 实例复用，配置变更自动热重载
 */
export default function Chat({ embedded = false }: ChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 设置弹窗状态
  const [showSettings, setShowSettings] = useState(false)
  // 当前激活的 Agent 人设信息
  const [agentInfo, setAgentInfo] = useState<{ name: string; avatar: string }>({
    name: 'HomeHamster',
    avatar: '🐹',
  })
  // 会话管理状态
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [showSidebar, setShowSidebar] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)

  // 使用 ref 保存 sessionId，供 useChat 的 fetch 闭包始终读取最新值
  const sessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  // ---- useChat 必须在回调定义之前调用，以获取 setMessages ----
  const { messages, setMessages, input, handleInputChange, handleSubmit, isLoading, error, reload } = useChat({
    api: '/api/agent/chat',

    // v3 核心：自定义 fetch 只发送 session_id + content，不再传全量 messages
    fetch: async (endpoint: string, options: RequestInit) => {
      const body = JSON.parse(options.body as string)
      // 提取最新的用户消息（useChat 会把所有消息都放进来，我们只取最后一条 user 消息）
      const userMessages = body.messages.filter((msg: any) => msg.role === 'user')
      const lastMessage = userMessages[userMessages.length - 1]

      // 发送到后端：只需要 session_id + content
      const response = await fetch(endpoint, {
        ...options,
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          content: lastMessage?.content || '',
          user_id: 'default',
        }),
      })

      if (!response.ok || !response.body) {
        return response
      }

      // 将后端 SSE 格式转换为 Vercel AI SDK 数据流格式
      const encoder = new TextEncoder()
      const decoder = new TextDecoder()
      const reader = response.body.getReader()
      let buffer = ''

      const stream = new ReadableStream({
        async start(controller) {
          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) break

              buffer += decoder.decode(value, { stream: true })
              const lines = buffer.split('\n')
              buffer = lines.pop() || ''

              for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed || !trimmed.startsWith('data: ')) continue

                const data = trimmed.slice(6)
                if (data === '[DONE]') {
                  controller.close()
                  return
                }

                try {
                  const parsed = JSON.parse(data)
                  if (parsed.content) {
                    const token = JSON.stringify(parsed.content)
                    controller.enqueue(encoder.encode(`0:${token}\n`))
                  }
                } catch {
                  // 忽略解析错误
                }
              }
            }
            controller.close()
          } catch (error) {
            controller.error(error)
          }
        },
      })

      return new Response(stream, {
        headers: response.headers,
        status: response.status,
        statusText: response.statusText,
      })
    },

    initialMessages: [],
  })

  // ---- 会话管理回调（setMessages 已可用） ----

  // 加载激活的 Agent 人设
  useEffect(() => {
    (async () => {
      try {
        const agent = await getActiveAgent()
        if (agent) {
          setAgentInfo({ name: agent.name, avatar: agent.avatar })
        }
      } catch {
        // 接口未就绪时使用默认值
      }
    })()
  }, [])

  // 加载会话列表
  const loadSessions = async () => {
    try {
      const list = await listSessions()
      setSessions(list)
    } catch {
      // 忽略错误
    }
  }

  // 创建新会话
  const handleNewSession = async () => {
    setSessionLoading(true)
    try {
      const session = await createSession({ user_id: 'default' })
      setSessionId(session.session_id)
      setMessages([])
      await loadSessions()
    } catch (e) {
      console.error('创建会话失败:', e)
    } finally {
      setSessionLoading(false)
    }
  }

  // 切换会话
  const handleSwitchSession = async (sid: string) => {
    setSessionLoading(true)
    try {
      const data = await getSessionMessages(sid)
      setSessionId(sid)
      // 将数据库消息转换为 useChat 格式
      const chatMessages = data.messages
        .filter((m: ChatMessageRecord) => m.role === 'user' || m.role === 'assistant')
        .map((m: ChatMessageRecord) => ({
          id: `history-${m.id}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
        }))
      setMessages(chatMessages)
      setShowSidebar(false)
    } catch (e) {
      console.error('加载会话消息失败:', e)
    } finally {
      setSessionLoading(false)
    }
  }

  // 删除会话
  const handleDeleteSession = async (sid: string) => {
    try {
      await deleteSession(sid)
      if (sid === sessionId) {
        await handleNewSession()
      }
      await loadSessions()
    } catch (e) {
      console.error('删除会话失败:', e)
    }
  }

  // 初始化：加载会话列表 + 自动创建或恢复会话
  useEffect(() => {
    (async () => {
      await loadSessions()

      // 尝试从 localStorage 恢复上次会话
      const savedSessionId = localStorage.getItem('hh_session_id')
      if (savedSessionId) {
        try {
          await handleSwitchSession(savedSessionId)
          return
        } catch {
          // 恢复失败则创建新会话
        }
      }
      await handleNewSession()
    })()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // 保存 session_id 到 localStorage
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('hh_session_id', sessionId)
    }
  }, [sessionId])

  // 对话完成后刷新会话列表（更新最后消息预览）
  const prevLoadingRef = useRef(false)
  useEffect(() => {
    if (prevLoadingRef.current && !isLoading && sessionId) {
      loadSessions()
    }
    prevLoadingRef.current = isLoading
  }, [isLoading, sessionId])

  // 自动滚动到消息底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // 输入框自适应高度
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
    }
  }, [input])

  // 处理回车发送（Shift+Enter 换行）
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !isLoading && sessionId) {
        handleSubmit(e as any)
      }
    }
  }

  // 处理设置中 Agent 变更
  const handleAgentChange = (agent: AgentConfig) => {
    setAgentInfo({ name: agent.name, avatar: agent.avatar })
  }

  return (
    <div className={`flex h-full ${embedded ? '' : 'h-screen bg-gradient-to-b from-orange-50 to-amber-50'}`}>
      {/* ===== 会话侧边栏 ===== */}
      <SessionSidebar
        sessions={sessions}
        currentSessionId={sessionId}
        visible={showSidebar}
        loading={sessionLoading}
        onNewSession={handleNewSession}
        onSwitchSession={handleSwitchSession}
        onDeleteSession={handleDeleteSession}
        onClose={() => setShowSidebar(false)}
      />

      {/* ===== 主对话区域 ===== */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* ===== 顶部标题栏 ===== */}
        {!embedded && (
          <header className="flex items-center justify-between px-4 py-3 bg-white/80 backdrop-blur-md border-b border-orange-100 shadow-sm">
            <div className="flex items-center gap-2">
              {/* 会话列表按钮 */}
              <button
                onClick={() => setShowSidebar(!showSidebar)}
                className="w-9 h-9 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-600 transition-colors"
                title="会话列表"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <img
                src="/hamsters/logo.png"
                alt="Hamster"
                className="w-9 h-9 rounded-full object-cover ring-2 ring-orange-200"
              />
              <div>
                <h1 className="text-lg font-bold text-gray-800">{agentInfo.name}</h1>
                <p className="text-xs text-gray-500">家庭管理 Agent</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isLoading && (
                <span className="flex items-center gap-1.5 text-sm text-orange-500">
                  <span className="inline-block w-2 h-2 bg-orange-400 rounded-full animate-pulse" />
                  思考中...
                </span>
              )}
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
            </div>
          </header>
        )}

        {/* 嵌入模式下的简化头部 */}
        {embedded && (
          <div className="flex items-center justify-between px-4 py-2 border-b border-orange-100 bg-white/50">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500"
              title="会话列表"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <img src="/hamsters/logo.png" alt="Hamster" className="w-7 h-7 rounded-full object-cover" />
              <span className="text-sm font-medium text-gray-700">{agentInfo.name}</span>
            </div>
            <button
              onClick={() => setShowSettings(true)}
              className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500"
              title="设置"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        )}

        {/* ===== 消息列表区域 ===== */}
        <div className="flex-1 overflow-y-auto chat-scrollbar px-4 py-6">
          <div className="max-w-3xl mx-auto space-y-4">
            {/* 欢迎消息（无消息时显示） */}
            {messages.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <img src="/hamsters/logo.png" alt="Hamster" className="w-20 h-20 rounded-full object-cover ring-4 ring-orange-100 mb-4 animate-bounce" style={{ animationDuration: '2s' }} />
                <h2 className="text-xl font-bold text-gray-800 mb-2">你好！我是 {agentInfo.name}</h2>
                <p className="text-gray-500 text-sm max-w-md">
                  你的家庭管理小助手！可以帮你记账、查库存、提供采购建议。
                  <br />试试对我说：&quot;帮我记一笔，午餐花了25元&quot;
                </p>
              </div>
            )}

            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} message-fade-in`}
              >
                <div
                  className={`flex gap-3 max-w-[85%] ${
                    message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                  }`}
                >
                  {/* 头像 */}
                  <div
                    className={`flex-shrink-0 w-9 h-9 rounded-full overflow-hidden ${
                      message.role === 'user'
                        ? 'bg-blue-100'
                        : 'bg-orange-100 ring-2 ring-orange-200'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <span className="flex items-center justify-center w-full h-full text-lg">👤</span>
                    ) : (
                      <img src="/hamsters/logo.png" alt="AI" className="w-full h-full object-cover" />
                    )}
                  </div>

                  {/* 消息气泡 */}
                  <div
                    className={`rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-blue-500 text-white rounded-tr-sm'
                        : 'bg-white text-gray-800 rounded-tl-sm shadow-sm border border-gray-100'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                        {message.content}
                      </p>
                    ) : (
                      <div
                        className={`prose prose-sm max-w-none ${
                          isLoading && message.id === messages[messages.length - 1]?.id
                            ? 'typing-cursor'
                            : ''
                        }`}
                      >
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => (
                              <p className="whitespace-pre-wrap break-words text-sm leading-relaxed mb-2 last:mb-0">
                                {children}
                              </p>
                            ),
                            ul: ({ children }) => (
                              <ul className="text-sm leading-relaxed list-disc pl-4 mb-2">
                                {children}
                              </ul>
                            ),
                            ol: ({ children }) => (
                              <ol className="text-sm leading-relaxed list-decimal pl-4 mb-2">
                                {children}
                              </ol>
                            ),
                            code: ({ inline, children }: any) =>
                              inline ? (
                                <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono text-orange-600">
                                  {children}
                                </code>
                              ) : (
                                <pre className="bg-gray-800 text-gray-100 rounded-lg p-3 my-2 overflow-x-auto">
                                  <code className="text-xs font-mono">{children}</code>
                                </pre>
                              ),
                            strong: ({ children }) => (
                              <strong className="font-semibold text-gray-900">{children}</strong>
                            ),
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* 加载中的打字指示器 */}
            {isLoading && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex justify-start message-fade-in">
                <div className="flex gap-3 max-w-[85%]">
                  <div className="flex-shrink-0 w-9 h-9 rounded-full bg-orange-100 overflow-hidden ring-2 ring-orange-200">
                    <img src="/hamsters/think.png" alt="思考中" className="w-full h-full object-cover" />
                  </div>
                  <div className="bg-white rounded-2xl rounded-tl-sm shadow-sm border border-gray-100 px-4 py-3">
                    <div className="flex gap-1">
                      <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="inline-block w-2 h-2 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 错误提示 */}
            {error && (
              <div className="flex justify-center">
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-600">
                  ⚠️ 连接出错：{error.message}
                  <button
                    onClick={() => reload()}
                    className="ml-2 underline hover:text-red-700"
                  >
                    重试
                  </button>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ===== 底部输入区域 ===== */}
        <div className="border-t border-orange-100 bg-white/80 backdrop-blur-md px-4 py-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={`和 ${agentInfo.name} 说点什么... (Enter 发送, Shift+Enter 换行)`}
                  rows={1}
                  disabled={isLoading || !sessionId}
                  className="w-full resize-none rounded-2xl border border-gray-200 bg-white px-4 py-3 pr-12 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  style={{ minHeight: '48px', maxHeight: '120px' }}
                />
              </div>

              <button
                onClick={(e) => {
                  if (input.trim() && !isLoading && sessionId) {
                    handleSubmit(e)
                  }
                }}
                disabled={!input.trim() || isLoading || !sessionId}
                className="flex-shrink-0 w-12 h-12 rounded-2xl bg-orange-500 hover:bg-orange-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors shadow-md hover:shadow-lg"
                title={isLoading ? '停止' : '发送'}
              >
                {isLoading ? (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
              </button>
            </div>

            <div className="flex gap-2 mt-2 flex-wrap">
              {[
                '帮我记一笔，午餐花了25元',
                '查看家里有什么食品',
                '本月花了多少钱？',
                '添加一个"文具"类别',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    const event = {
                      target: { value: suggestion },
                    } as React.ChangeEvent<HTMLTextAreaElement>
                    handleInputChange(event)
                    setTimeout(() => {
                      handleSubmit({ preventDefault: () => {} } as React.FormEvent)
                    }, 50)
                  }}
                  disabled={isLoading || !sessionId}
                  className="text-xs px-3 py-1.5 rounded-full bg-orange-50 hover:bg-orange-100 text-orange-600 border border-orange-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        </div>
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
