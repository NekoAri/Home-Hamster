'use client'

import { useChat } from 'ai/react'
import { useRef, useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import Settings from './Settings'
import { getActiveAgent, type AgentConfig } from '@/lib/api'

interface ChatProps {
  /** 嵌入模式：不渲染自身顶部栏（由外层统一管理导航） */
  embedded?: boolean
}

/**
 * HomeHamster 对话组件
 *
 * 使用 Vercel AI SDK 的 useChat Hook 对接后端 SSE 流式接口
 * 特色：
 * - 动态加载 Agent 人设配置（名字、头像），来自数据库配置
 * - 集成设置弹窗，可配置 LLM 供应商和 Agent 人设
 * - 消息列表展示（用户/AI 消息区分样式）
 * - 打字机流式输出效果（光标闪烁）
 * - 自动滚动到最新消息
 * - Markdown 渲染支持
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

  // 加载激活的 Agent 人设
  const loadAgent = useCallback(async () => {
    try {
      const agent = await getActiveAgent()
      if (agent) {
        setAgentInfo({ name: agent.name, avatar: agent.avatar })
      }
    } catch {
      // 接口未就绪时使用默认值
    }
  }, [])

  useEffect(() => {
    loadAgent()
  }, [loadAgent])

  const { messages, input, handleInputChange, handleSubmit, isLoading, error, reload } = useChat({
    // 后端 SSE 接口地址（通过 next.config.js 代理到后端）
    api: '/api/agent/chat',

    // 自定义 fetch：将 useChat 的消息格式转换为后端所需格式，并处理 SSE 响应
    fetch: async (endpoint: string, options: RequestInit) => {
      // 解析 useChat 发送的请求体，提取并精简消息格式
      const body = JSON.parse(options.body as string)
      const cleanMessages = body.messages
        // 过滤掉系统消息（后端会自行添加系统提示词）
        .filter((msg: any) => msg.role !== 'system')
        // 只保留后端需要的字段
        .map((msg: any) => ({
          role: msg.role,
          content: msg.content,
        }))

      // 发送请求到后端
      const response = await fetch(endpoint, {
        ...options,
        body: JSON.stringify({
          messages: cleanMessages,
          user_id: 'default',
        }),
      })

      // 如果响应不是流式，直接返回（如错误响应）
      if (!response.ok || !response.body) {
        return response
      }

      // 将后端 SSE 格式转换为 Vercel AI SDK 所需的数据流格式
      // 后端格式: data: {"content": "token"}\n\n
      // AI SDK 格式: 0:"token"\n  （0: 表示文本类型）
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

              // 按行解析 SSE 数据
              const lines = buffer.split('\n')
              // 最后一行可能不完整，保留在 buffer 中
              buffer = lines.pop() || ''

              for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed || !trimmed.startsWith('data: ')) continue

                const data = trimmed.slice(6) // 去掉 "data: " 前缀

                // 结束标记
                if (data === '[DONE]') {
                  controller.close()
                  return
                }

                try {
                  const parsed = JSON.parse(data)
                  if (parsed.content) {
                    // 转换为 AI SDK 数据流格式: 0:"token"\n
                    const token = JSON.stringify(parsed.content)
                    controller.enqueue(encoder.encode(`0:${token}\n`))
                  }
                } catch {
                  // 忽略解析错误的行
                }
              }
            }
            controller.close()
          } catch (error) {
            controller.error(error)
          }
        },
      })

      // 返回转换后的 Response 对象
      return new Response(stream, {
        headers: response.headers,
        status: response.status,
        statusText: response.statusText,
      })
    },

    // 初始消息（使用 Agent 人设名字）
    initialMessages: [
      {
        id: 'welcome',
        role: 'assistant',
        content: `${agentInfo.avatar} 你好！我是 **${agentInfo.name}**，你的家庭管理小助手！\n\n我可以帮你：\n- 📊 记录家庭账目（支出/收入）\n- 📦 查询和管理物品库存\n- 💡 提供资金使用和采购建议\n\n试试对我说：*"帮我记一笔，午餐花了25元"*`,
      },
    ],
  })

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
      if (input.trim() && !isLoading) {
        handleSubmit(e as any)
      }
    }
  }

  // 处理设置中 Agent 变更
  const handleAgentChange = (agent: AgentConfig) => {
    setAgentInfo({ name: agent.name, avatar: agent.avatar })
  }

  return (
    <div className={`flex flex-col h-full ${embedded ? '' : 'h-screen bg-gradient-to-b from-orange-50 to-amber-50'}`}>
      {/* ===== 顶部标题栏（仅在非嵌入模式下渲染） ===== */}
      {!embedded && (
        <header className="flex items-center justify-between px-6 py-4 bg-white/80 backdrop-blur-md border-b border-orange-100 shadow-sm">
            <div className="flex items-center gap-3">
            <img
              src="/hamsters/logo.png"
              alt="Hamster"
              className="w-10 h-10 rounded-full object-cover ring-2 ring-orange-200"
            />
            <div>
              <h1 className="text-xl font-bold text-gray-800">{agentInfo.name}</h1>
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
            {/* 设置按钮 */}
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

      {/* ===== 消息列表区域 ===== */}
      <div className="flex-1 overflow-y-auto chat-scrollbar px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
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

          {/* 滚动锚点 */}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ===== 底部输入区域 ===== */}
      <div className="border-t border-orange-100 bg-white/80 backdrop-blur-md px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2">
            {/* 输入框 */}
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={`和 ${agentInfo.name} 说点什么... (Enter 发送, Shift+Enter 换行)`}
                rows={1}
                disabled={isLoading}
                className="w-full resize-none rounded-2xl border border-gray-200 bg-white px-4 py-3 pr-12 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                style={{ minHeight: '48px', maxHeight: '120px' }}
              />
            </div>

            {/* 发送/停止按钮 */}
            <button
              onClick={(e) => {
                if (input.trim() && !isLoading) {
                  handleSubmit(e)
                }
              }}
              disabled={!input.trim() || isLoading}
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

          {/* 快捷操作按钮 */}
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
                disabled={isLoading}
                className="text-xs px-3 py-1.5 rounded-full bg-orange-50 hover:bg-orange-100 text-orange-600 border border-orange-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {suggestion}
              </button>
            ))}
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
