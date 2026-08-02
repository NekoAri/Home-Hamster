<template>
  <div class="page">
    <div class="page-header">
      <span class="page-title">{{ $t('statsTitle') }}</span>
    </div>

    <!-- 分类统计图表 -->
    <div class="card">
      <div class="chart-title">📊 {{ $t('byCategory') }}</div>
      <div v-if="categoryStats.length > 0" class="category-list">
        <div v-for="cat in categoryStats" :key="cat.id" class="cat-stat-item">
          <div class="cat-info">
            <span class="cat-icon">{{ cat.icon }}</span>
            <div>
              <div class="cat-name">{{ cat.name }}</div>
              <div class="cat-count">{{ $t('itemsCount', { count: cat.item_count, stock: cat.total_stock }) }}</div>
            </div>
          </div>
          <div class="cat-bar-wrap">
            <div class="cat-bar" :style="{ width: getCategoryPercent(cat.total_stock) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 临期物品列表（只显示前3条） -->
    <div id="sec-expiring" class="card">
      <div class="section-header">
        <div class="chart-title">⚠️ {{ $t('expiringItems') }}</div>
        <router-link v-if="expiringItems.length > 3" to="/expiring" class="more-link">
          {{ $t('viewMore') }} ({{ expiringItems.length }}) ›
        </router-link>
      </div>
      <div v-if="expiringItems.length > 0">
        <div v-for="item in expiringItems.slice(0, 3)" :key="item.inv_id" class="alert-row" @click="$router.push('/item/' + item.item_id)">
          <span class="alert-icon">{{ item.category_icon || '📦' }}</span>
          <div class="alert-info">
            <div class="alert-name">{{ item.name }}</div>
            <div class="alert-meta">{{ item.expiry_date }} · {{ $t('expiryInfo', { date: item.expiry_date, qty: item.quantity, unit: item.unit }) }}</div>
          </div>
          <span class="badge" :class="item.days_left <= 0 ? 'badge-danger' : item.days_left <= 7 ? 'badge-danger' : 'badge-warning'">
            {{ item.days_left <= 0 ? $t('expired') : $t('daysText', { days: item.days_left }) }}
          </span>
        </div>
        <router-link v-if="expiringItems.length > 3" to="/expiring" class="view-all-row">
          {{ $t('viewMore') }} {{ expiringItems.length - 3 }} {{ $t('noData') !== '暂无数据' ? 'more items' : '条' }} ›
        </router-link>
      </div>
      <div v-else class="empty-small">{{ $t('noExpiring') }}</div>
    </div>

    <!-- 库存不足列表（只显示前3条） -->
    <div id="sec-lowstock" class="card">
      <div class="section-header">
        <div class="chart-title">📉 {{ $t('lowStockList') }}</div>
        <router-link v-if="lowStockItems.length > 3" to="/inventory?filter=low" class="more-link">
          {{ $t('viewMore') }} ({{ lowStockItems.length }}) ›
        </router-link>
      </div>
      <div v-if="lowStockItems.length > 0">
        <div v-for="item in lowStockItems.slice(0, 3)" :key="item.id" class="alert-row" @click="$router.push('/item/' + item.id)">
          <span class="alert-icon">{{ item.category_icon || '📦' }}</span>
          <div class="alert-info">
            <div class="alert-name">{{ item.name }}</div>
            <div class="alert-meta">{{ $t('stockInfo', { cur: item.total_stock, unit: item.unit, min: item.min_stock }) }}</div>
          </div>
          <span class="badge badge-danger">{{ $t('insufficient') }}</span>
        </div>
      </div>
      <div v-else class="empty-small">{{ $t('stockSufficient') }}</div>
    </div>

    <!-- 消耗趋势图 -->
    <div class="card">
      <div class="chart-title">📈 {{ $t('consumptionTrend') }}</div>
      <canvas ref="trendChart" height="200"></canvas>
      <div v-if="consumptionData.length === 0" class="empty-small">{{ $t('noConsumption') }}</div>
    </div>

    <!-- 补货建议 -->
    <div class="card">
      <div class="chart-title">💡 {{ $t('restockSuggestion') }}</div>
      <div v-if="suggestions.length > 0">
        <div v-for="item in suggestions" :key="item.id" class="suggest-row" @click="$router.push('/item/' + item.id)">
          <div class="suggest-info">
            <div class="suggest-name">{{ item.name }}</div>
            <div class="suggest-meta">
              {{ $t('expiryInfo', { date: '', qty: item.total_stock, unit: item.unit }).split('·')[0].trim() }} ·
              {{ $t('dailyAvg', { avg: item.avg_daily, unit: item.unit }) }} ·
              {{ $t('daysRemaining', { days: item.days_remaining }) }}
            </div>
          </div>
          <span class="badge" :class="item.status === 'urgent' ? 'badge-danger' : 'badge-warning'">
            {{ item.status === 'urgent' ? $t('urgent') : $t('restock') }}
          </span>
        </div>
      </div>
      <div v-else class="empty-small">{{ $t('noSuggestion') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, inject } from 'vue'
import { useRoute } from 'vue-router'
import Chart from 'chart.js/auto'
import { api } from '../api/index.js'

const route = useRoute()
const t = inject('t')
const categoryStats = ref([])
const expiringItems = ref([])
const lowStockItems = ref([])
const suggestions = ref([])
const consumptionData = ref([])
const trendChart = ref(null)

const getCategoryPercent = (stock) => {
  const max = Math.max(...categoryStats.value.map(c => c.total_stock), 1)
  return (stock / max) * 100
}

const initChart = () => {
  if (!trendChart.value || consumptionData.value.length === 0) return
  
  const ctx = trendChart.value.getContext('2d')
  const labels = consumptionData.value.map(d => d.date.slice(5))
  const data = consumptionData.value.map(d => d.consumed)
  
  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: t('consumptionLabel'),
        data,
        borderColor: '#4F46E5',
        backgroundColor: 'rgba(79,70,229,0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: '#E5E7EB' } },
        x: { grid: { display: false } }
      }
    }
  })
}

onMounted(async () => {
  const [cats, exp, low, sug, cons] = await Promise.all([
    api.getByCategory(),
    api.getExpiring(30),
    api.getLowStock(),
    api.getSuggestions(),
    api.getConsumption(30)
  ])
  
  categoryStats.value = cats.data
  expiringItems.value = exp.data
  lowStockItems.value = low.data
  suggestions.value = sug.data
  consumptionData.value = cons.data
  
  await nextTick()
  initChart()

  // 根据首页点击的 tab 参数滚动到对应区域
  const tab = route.query.tab
  if (tab) {
    await nextTick()
    const targetMap = { expiring: 'sec-expiring', expired: 'sec-expiring', lowstock: 'sec-lowstock' }
    const el = document.getElementById(targetMap[tab])
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
</script>

<style scoped>
.chart-title { font-weight: 700; font-size: 16px; }

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.more-link {
  font-size: 13px;
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}
.view-all-row {
  display: block;
  text-align: center;
  padding: 12px 0 4px;
  font-size: 13px;
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
  border-top: 1px solid var(--border);
  margin-top: 4px;
}

.category-list { display: flex; flex-direction: column; gap: 12px; }
.cat-stat-item { display: flex; flex-direction: column; gap: 8px; }
.cat-info { display: flex; align-items: center; gap: 10px; }
.cat-icon { font-size: 24px; }
.cat-name { font-weight: 600; }
.cat-count { font-size: 12px; color: var(--text-muted); }
.cat-bar-wrap {
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}
.cat-bar {
  height: 100%;
  background: var(--primary);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.alert-row, .suggest-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.alert-row:last-child, .suggest-row:last-child { border-bottom: none; }
.alert-icon { font-size: 24px; }
.alert-info, .suggest-info { flex: 1; min-width: 0; }
.alert-name, .suggest-name { font-weight: 600; font-size: 14px; }
.alert-meta, .suggest-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.empty-small { text-align: center; padding: 20px; color: var(--text-muted); font-size: 14px; }
</style>
