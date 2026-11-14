'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  listReports,
  getLatestReport,
  sendReportNow,
  getReportSettings,
  updateReportSettings,
  listEvents,
  completeEvent,
  snoozeEvent,
  dismissEvent,
  type DailyReport,
  type ReportSettings,
  type HomeEvent,
} from '@/lib/api'

/**
 * 今日简报视图（P1）
 *
 * 展示每天由后端定时生成的早报（与推送同一份数据结构）：
 * - 最新简报卡片：管家口吻正文 + 原始数据明细
 * - 历史早报列表
 * - 早报设置（开关/发送时间）与手动发送
 */
export default function ReportsView() {
  const [latest, setLatest] = useState<DailyReport | null>(null)
  const [reports, setReports] = useState<DailyReport[]>([])
  const [events, setEvents] = useState<HomeEvent[]>([])
  const [settings, setSettings] = useState<ReportSettings>({ enabled: true, hour: 8, minute: 0 })
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [lt, list, st, evts] = await Promise.all([
        getLatestReport(),
        listReports(30),
        getReportSettings(),
        listEvents('pending', 50),
      ])
      setLatest(lt)
      setReports(list)
      setSettings(st)
      setEvents(evts)
    } catch (err) {
      console.error('加载简报失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const handleSendNow = async () => {
    setSending(true)
    try {
      const result = await sendReportNow()
      showToast(result.message)
      if (result.ok) await load()
    } catch (err) {
      console.error('发送失败:', err)
      showToast('发送失败，请稍后再试')
    } finally {
      setSending(false)
    }
  }

  const handleSaveSettings = async () => {
    setSavingSettings(true)
    try {
      const saved = await updateReportSettings(settings)
      setSettings(saved)
      showToast(saved.enabled
        ? `已保存，每天 ${String(saved.hour).padStart(2, '0')}:${String(saved.minute).padStart(2, '0')} 发送`
        : '已保存，每日简报已关闭')
    } catch (err) {
      console.error('保存设置失败:', err)
      showToast('保存失败，请稍后再试')
    } finally {
      setSavingSettings(false)
    }
  }

  const handleEventAction = async (id: number, action: 'complete' | 'snooze' | 'dismiss') => {
    try {
      if (action === 'complete') await completeEvent(id)
      else if (action === 'snooze') await snoozeEvent(id, 24)
      else await dismissEvent(id)
      setEvents((prev) => prev.filter((e) => e.id !== id))
      showToast(action === 'complete' ? '已完成' : action === 'snooze' ? '明天再提醒你' : '已忽略')
    } catch (err) {
      console.error('操作失败:', err)
      showToast('操作失败，请稍后再试')
    }
  }

  const reportBody = (r: DailyReport) => r.polished_text || r.template_text

  return (
    <div className="space-y-6">
      {/* ===== 最新简报卡片 ===== */}
      <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="flex items-center gap-2 text-lg font-bold text-gray-800">
            <span>🐹</span>
            <span>今日简报</span>
          </h2>
          <button
            onClick={handleSendNow}
            disabled={sending}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {sending ? '发送中…' : '立即发送'}
          </button>
        </div>

        {loading ? (
          <div className="py-10 text-center text-gray-400 text-sm">加载中…</div>
        ) : !latest ? (
          <div className="py-10 text-center text-gray-400 text-sm">
            还没有简报记录。点击「立即发送」生成第一条，或等待每天定时推送。
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
              <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                {latest.report_date}
              </span>
              <span className={`px-2 py-0.5 rounded-full font-medium ${
                latest.status === 'sent'
                  ? 'bg-green-100 text-green-700'
                  : latest.status === 'failed'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {latest.status === 'sent' ? '已推送' : latest.status === 'failed' ? '推送失败' : '待发送'}
              </span>
              <span className={`px-2 py-0.5 rounded-full font-medium ${
                latest.is_polished ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
              }`}>
                {latest.is_polished ? 'AI 润色版' : '模板版'}
              </span>
              {latest.trigger_type === 'manual' && (
                <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">手动触发</span>
              )}
              {latest.fail_reason && (
                <span className="text-red-500">失败原因：{latest.fail_reason}</span>
              )}
            </div>

            <p className="whitespace-pre-line text-gray-700 leading-relaxed">
              {reportBody(latest)}
            </p>
          </>
        )}
      </section>

      {/* ===== 待处理提醒（动作写回 events.status） ===== */}
      {events.length > 0 && (
        <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
          <h3 className="text-base font-bold text-gray-800 mb-4">
            待处理提醒 <span className="text-sm font-normal text-gray-400">（{events.length}）</span>
          </h3>
          <ul className="space-y-3">
            {events.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 rounded-xl bg-orange-50/60 px-3.5 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{e.title}</p>
                  {e.detail && <p className="text-xs text-gray-500 mt-0.5 truncate">{e.detail}</p>}
                  <p className="text-xs text-gray-400 mt-0.5">
                    {{ expiry: '临期', low_stock: '库存', bill: '交费', maintenance: '维护', todo: '待办' }[e.kind] || '提醒'}
                    {e.payload?.remind_count ? ` · 已提醒 ${e.payload.remind_count} 次` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => handleEventAction(e.id, 'complete')}
                    className="px-2.5 py-1 rounded-lg bg-green-500 hover:bg-green-600 text-white text-xs font-medium transition-colors"
                  >
                    完成
                  </button>
                  <button
                    onClick={() => handleEventAction(e.id, 'snooze')}
                    className="px-2.5 py-1 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 text-xs font-medium transition-colors"
                  >
                    稍后
                  </button>
                  <button
                    onClick={() => handleEventAction(e.id, 'dismiss')}
                    className="px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-400 text-xs font-medium transition-colors"
                  >
                    忽略
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ===== 数据明细 ===== */}
      {latest?.data && <ReportDataDetail data={latest.data} />}

      {/* ===== 早报设置 ===== */}
      <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
        <h3 className="text-base font-bold text-gray-800 mb-4">推送设置</h3>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              className="w-4 h-4 accent-orange-500"
            />
            <span className="text-sm text-gray-700">每天定时推送简报</span>
          </label>
          {settings.enabled && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              发送时间
              <input
                type="time"
                value={`${String(settings.hour).padStart(2, '0')}:${String(settings.minute).padStart(2, '0')}`}
                onChange={(e) => {
                  const [h, m] = e.target.value.split(':').map(Number)
                  setSettings({ ...settings, hour: h || 0, minute: m || 0 })
                }}
                className="px-2 py-1 rounded-lg border border-orange-200 text-sm focus:outline-none focus:ring-2 focus:ring-orange-200"
              />
            </label>
          )}
          <button
            onClick={handleSaveSettings}
            disabled={savingSettings}
            className="px-3.5 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {savingSettings ? '保存中…' : '保存设置'}
          </button>
        </div>
        <p className="mt-3 text-xs text-gray-400">
          推送通过「设置 → 通知渠道」中启用的渠道发送（如 Bark）；未配置渠道时简报只记录在下方，不会推送手机。
        </p>
      </section>

      {/* ===== 历史早报 ===== */}
      <section className="bg-white rounded-2xl shadow-sm border border-orange-100 p-5 sm:p-6">
        <h3 className="text-base font-bold text-gray-800 mb-4">历史简报</h3>
        {reports.length === 0 ? (
          <div className="py-6 text-center text-gray-400 text-sm">暂无历史记录</div>
        ) : (
          <ul className="divide-y divide-orange-50">
            {reports.map((r) => (
              <li key={r.id} className="py-3">
                <button
                  onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  className="w-full text-left flex items-center justify-between gap-3"
                >
                  <span className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-gray-700">{r.report_date}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      r.status === 'sent'
                        ? 'bg-green-50 text-green-600'
                        : r.status === 'failed'
                        ? 'bg-red-50 text-red-600'
                        : 'bg-gray-50 text-gray-500'
                    }`}>
                      {r.status === 'sent' ? '已推送' : r.status === 'failed' ? '失败' : '待发'}
                    </span>
                    <span className="text-xs text-gray-400">{r.is_polished ? '润色' : '模板'}</span>
                  </span>
                  <span className="text-xs text-gray-400 truncate max-w-[50%]">
                    {reportBody(r).split('\n')[0]}
                  </span>
                </button>
                {expandedId === r.id && (
                  <div className="mt-3 pl-1">
                    <p className="whitespace-pre-line text-sm text-gray-600 leading-relaxed">
                      {reportBody(r)}
                    </p>
                    <details className="mt-3">
                      <summary className="text-xs text-gray-400 cursor-pointer hover:text-orange-500">
                        查看原始数据
                      </summary>
                      <div className="mt-2">
                        <ReportDataDetail data={r.data} compact />
                      </div>
                    </details>
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

// ============================================================
// 数据明细（金额/库存数字全部来自后端聚合结果，前端不推算）
// ============================================================

function ReportDataDetail({
  data,
  compact = false,
}: {
  data: DailyReport['data']
  compact?: boolean
}) {
  const hasAny =
    (data.expired?.length || 0) +
      (data.expiring?.length || 0) +
      (data.low_stock?.length || 0) +
      (data.events?.length || 0) >
    0 || !!data.expense

  if (!hasAny) return null

  return (
    <section className={`bg-white rounded-2xl shadow-sm border border-orange-100 ${compact ? 'p-4' : 'p-5 sm:p-6'}`}>
      {!compact && <h3 className="text-base font-bold text-gray-800 mb-4">数据明细</h3>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        {!!data.expense && (
          <div className="rounded-xl bg-amber-50 p-3">
            <p className="text-xs text-gray-500 mb-1">本月支出</p>
            <p className="font-semibold text-gray-800">¥{data.expense.this_month.toFixed(2)}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              上月同期 ¥{data.expense.prev_month_same_period.toFixed(2)}
            </p>
          </div>
        )}
        {!!data.expired?.length && (
          <div className="rounded-xl bg-red-50 p-3">
            <p className="text-xs text-gray-500 mb-1">已过期</p>
            {data.expired.map((i, idx) => (
              <p key={idx} className="text-gray-700">
                {i.name}（{i.quantity}{i.unit}）
              </p>
            ))}
          </div>
        )}
        {!!data.expiring?.length && (
          <div className="rounded-xl bg-orange-50 p-3">
            <p className="text-xs text-gray-500 mb-1">即将到期</p>
            {data.expiring.map((i, idx) => (
              <p key={idx} className="text-gray-700">
                {i.name} · {i.expiry_date}
              </p>
            ))}
          </div>
        )}
        {!!data.low_stock?.length && (
          <div className="rounded-xl bg-blue-50 p-3">
            <p className="text-xs text-gray-500 mb-1">库存偏低</p>
            {data.low_stock.map((i, idx) => (
              <p key={idx} className="text-gray-700">
                {i.name}（剩 {i.quantity}{i.unit}）
              </p>
            ))}
          </div>
        )}
        {!!data.events?.length && (
          <div className="rounded-xl bg-purple-50 p-3">
            <p className="text-xs text-gray-500 mb-1">未来几天的事</p>
            {data.events.map((e, idx) => (
              <p key={idx} className="text-gray-700">
                {e.title} {e.due_date ? `· ${e.due_date}` : ''}
              </p>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
