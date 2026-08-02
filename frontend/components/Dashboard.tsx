'use client'

import { useState, useEffect, useCallback } from 'react'
import AccountView from './AccountView'
import InventoryView from './InventoryView'
import CategoryView from './CategoryView'
import { getOverview, getInventoryStats, type OverviewData, type InventoryStats } from '@/lib/api'

type Tab = 'overview' | 'accounts' | 'inventory' | 'categories'

/**
 * Dashboard 普通模式容器
 *
 * 提供数据管理界面，无需通过 Agent 对话即可直接操作数据：
 * - 概览：总支出/收入、分类汇总、库存预警、临期提醒
 * - 账目管理：表格展示、筛选、分页、增删改
 * - 物品管理：表格展示、筛选、分页、增删改
 * - 类别管理：列表展示、增删改
 */
export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  // 概览数据
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [invStats, setInvStats] = useState<InventoryStats | null>(null)
  const [loading, setLoading] = useState(false)

  // 加载概览数据
  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, is] = await Promise.all([getOverview(), getInventoryStats()])
      setOverview(ov)
      setInvStats(is)
    } catch (err) {
      console.error('加载概览失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'overview') {
      loadOverview()
    }
  }, [activeTab, loadOverview])

  // Tab 配置
  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'overview', label: '概览', icon: '📊' },
    { key: 'accounts', label: '账目管理', icon: '💰' },
    { key: 'inventory', label: '物品管理', icon: '📦' },
    { key: 'categories', label: '类别管理', icon: '🏷️' },
  ]

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-orange-50 to-amber-50">
      {/* ===== Tab 栏 ===== */}
      <div className="flex items-center gap-1 px-4 py-2 bg-white/60 backdrop-blur-sm border-b border-orange-100">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-orange-500 text-white shadow-sm'
                : 'text-gray-600 hover:bg-orange-50 hover:text-orange-600'
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ===== 内容区 ===== */}
      <div className="flex-1 overflow-y-auto chat-scrollbar p-4 sm:p-6">
        <div className="max-w-6xl mx-auto">
          {activeTab === 'overview' && (
            <OverviewPanel
              overview={overview}
              invStats={invStats}
              loading={loading}
              onRefresh={loadOverview}
            />
          )}
          {activeTab === 'accounts' && <AccountView />}
          {activeTab === 'inventory' && <InventoryView />}
          {activeTab === 'categories' && <CategoryView />}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 概览面板组件
// ============================================================

function OverviewPanel({
  overview,
  invStats,
  loading,
  onRefresh,
}: {
  overview: OverviewData | null
  invStats: InventoryStats | null
  loading: boolean
  onRefresh: () => void
}) {
  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex gap-1">
          <span className="inline-block w-3 h-3 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="inline-block w-3 h-3 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="inline-block w-3 h-3 bg-orange-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    )
  }

  if (!overview || !invStats) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <p>暂无数据</p>
        <button
          onClick={onRefresh}
          className="mt-4 px-4 py-2 rounded-lg bg-orange-500 text-white text-sm hover:bg-orange-600"
        >
          刷新
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="本月总支出"
          value={`¥${overview.total_expense.toFixed(2)}`}
          icon="💸"
          color="red"
        />
        <StatCard
          title="本月总收入"
          value={`¥${overview.total_income.toFixed(2)}`}
          icon="💰"
          color="green"
        />
        <StatCard
          title="净额"
          value={`¥${overview.net_amount.toFixed(2)}`}
          icon="📈"
          color={overview.net_amount >= 0 ? 'green' : 'red'}
        />
        <StatCard
          title="交易笔数"
          value={`${overview.transaction_count}`}
          icon="📝"
          color="blue"
        />
      </div>

      {/* 分类支出排行 + 库存统计 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 分类支出排行 */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <span>🏷️</span> 支出分类排行
          </h3>
          {overview.category_breakdown.length > 0 ? (
            <div className="space-y-3">
              {overview.category_breakdown.map((item, i) => {
                const maxTotal = overview.category_breakdown[0].total
                const pct = maxTotal > 0 ? (item.total / maxTotal) * 100 : 0
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-700">{item.category}</span>
                      <span className="text-gray-500">¥{item.total.toFixed(2)} ({item.count}笔)</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-orange-400 to-red-400 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-8">本月暂无支出记录</p>
          )}
        </div>

        {/* 库存统计 */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <span>📦</span> 库存概览
          </h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="text-center py-3 bg-blue-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-600">{invStats.total_items}</p>
              <p className="text-xs text-gray-500 mt-1">物品种类</p>
            </div>
            <div className="text-center py-3 bg-green-50 rounded-lg">
              <p className="text-2xl font-bold text-green-600">{invStats.total_quantity}</p>
              <p className="text-xs text-gray-500 mt-1">物品总数</p>
            </div>
          </div>

          {/* 预警提示 */}
          {invStats.low_stock_alerts.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-orange-600 mb-2">⚠️ 低库存预警 ({invStats.low_stock_alerts.length})</p>
              <div className="space-y-1">
                {invStats.low_stock_alerts.slice(0, 3).map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-xs bg-orange-50 rounded px-2 py-1">
                    <span className="text-gray-700">{item.name}</span>
                    <span className="text-orange-600 font-medium">{item.quantity} {item.unit}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {invStats.expiring_alerts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-red-600 mb-2">⏰ 临期预警 ({invStats.expiring_alerts.length})</p>
              <div className="space-y-1">
                {invStats.expiring_alerts.slice(0, 3).map((item) => (
                  <div key={item.id} className="flex items-center justify-between text-xs bg-red-50 rounded px-2 py-1">
                    <span className="text-gray-700">{item.name}</span>
                    <span className="text-red-600 font-medium">
                      {item.expiry_date ? new Date(item.expiry_date).toLocaleDateString('zh-CN') : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 近7天支出趋势 */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <span>📅</span> 近 7 天支出趋势
        </h3>
        {overview.daily_trend.length > 0 ? (
          <div className="flex items-end justify-between gap-2 h-32">
            {overview.daily_trend.map((day, i) => {
              const maxExpense = Math.max(...overview.daily_trend.map((d) => d.expense), 1)
              const height = (day.expense / maxExpense) * 100
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-gray-500">¥{day.expense.toFixed(0)}</span>
                  <div className="w-full flex-1 flex items-end">
                    <div
                      className="w-full bg-gradient-to-t from-orange-500 to-orange-300 rounded-t-md min-h-[4px]"
                      style={{ height: `${height}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400">
                    {day.date ? new Date(day.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : ''}
                  </span>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-8">暂无近期支出数据</p>
        )}
      </div>

      {/* 刷新按钮 */}
      <div className="flex justify-center">
        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-6 py-2 rounded-lg bg-white border border-orange-200 text-orange-600 text-sm hover:bg-orange-50 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新数据
        </button>
      </div>
    </div>
  )
}

/** 统计卡片子组件 */
function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string
  value: string
  icon: string
  color: 'red' | 'green' | 'blue' | 'orange'
}) {
  const colorMap = {
    red: 'from-red-50 to-red-100 text-red-600 border-red-200',
    green: 'from-green-50 to-green-100 text-green-600 border-green-200',
    blue: 'from-blue-50 to-blue-100 text-blue-600 border-blue-200',
    orange: 'from-orange-50 to-orange-100 text-orange-600 border-orange-200',
  }

  return (
    <div className={`bg-gradient-to-br ${colorMap[color]} rounded-xl border p-4`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{title}</p>
    </div>
  )
}
