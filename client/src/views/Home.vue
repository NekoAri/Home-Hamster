<template>
  <div class="home-page">
    <!-- 顶部 Banner -->
    <div class="home-banner">
      <div class="banner-text">
        <div class="greeting">{{ $t('greeting') }}</div>
        <div class="date-text">{{ dateText }}</div>
      </div>
      <img src="/hamster-logo.jpg" class="app-logo" alt="Home Hamster" />
    </div>

    <!-- 概览统计卡片 -->
    <div v-if="overview" class="stats-grid">
      <router-link to="/expiring?tab=expiring" class="stat-card" :class="{ 'stat-warn': overview.expiringSoon > 0 }">
        <div class="stat-icon">⚠️</div>
        <div class="stat-num">{{ overview.expiringSoon }}</div>
        <div class="stat-label">{{ $t('expiringSoon') }}</div>
      </router-link>
      <router-link to="/expiring?tab=expired" class="stat-card" :class="{ 'stat-danger': overview.expired > 0 }">
        <div class="stat-icon">🔴</div>
        <div class="stat-num">{{ overview.expired }}</div>
        <div class="stat-label">{{ $t('expired') }}</div>
      </router-link>
    </div>

    <!-- 临期预警 -->
    <div v-if="expiring.length > 0" class="card">
      <div class="section-title">
        <span class="section-title-text">🐹 {{ $t('expiringAlert') }}</span>
        <router-link to="/expiring" class="see-all">{{ $t('viewAll') }} ›</router-link>
      </div>
      <div v-for="item in expiring.slice(0, 5)" :key="item.inv_id" class="alert-item" @click="$router.push('/item/' + item.item_id)">
        <div class="alert-info">
          <span class="alert-icon">{{ item.category_icon || '📦' }}</span>
          <div>
            <div class="alert-name">{{ item.name }}</div>
            <div class="alert-meta">{{ $t('expiryInfo', { date: item.expiry_date, qty: item.quantity, unit: item.unit }) }}</div>
          </div>
        </div>
        <span class="badge" :class="item.days_left <= 0 ? 'badge-danger' : item.days_left <= 7 ? 'badge-danger' : 'badge-warning'">
          {{ item.days_left <= 0 ? $t('expired') : $t('daysText', { days: item.days_left }) }}
        </span>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="section-title-row">
      <span class="section-title-text">✨ 快捷操作</span>
    </div>
    <div class="quick-actions">
      <router-link to="/scan" class="quick-btn quick-primary">
        <span class="quick-emoji">📷</span>
        <span class="quick-label">{{ $t('scanToStock') }}</span>
      </router-link>
      <router-link to="/scan?mode=consume" class="quick-btn quick-orange">
        <span class="quick-emoji">🍽️</span>
        <span class="quick-label">{{ $t('scanToConsume') }}</span>
      </router-link>
      <router-link to="/add-item" class="quick-btn quick-green">
        <span class="quick-emoji">✏️</span>
        <span class="quick-label">{{ $t('manualAdd') }}</span>
      </router-link>
      <router-link to="/inventory" class="quick-btn quick-blue">
        <span class="quick-emoji">📋</span>
        <span class="quick-label">{{ $t('viewInventory') }}</span>
      </router-link>
      <router-link to="/stats" class="quick-btn quick-purple">
        <span class="quick-emoji">📊</span>
        <span class="quick-label">{{ $t('statsAnalysis') }}</span>
      </router-link>
      <router-link to="/settings" class="quick-btn quick-gray">
        <span class="quick-emoji">⚙️</span>
        <span class="quick-label">{{ $t('settings') }}</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const overview   = ref(null)
const expiring   = ref([])

const dateText = ref('')
const updateDate = () => {
  const locale = localStorage.getItem('app-locale') || 'zh-CN'
  dateText.value = new Date().toLocaleDateString(locale, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  })
}
updateDate()

onMounted(async () => {
  try {
    const [ov, exp] = await Promise.all([
      api.getOverview(),
      api.getExpiring(30),
    ])
    overview.value = ov.data
    expiring.value = exp.data
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.home-page {
  padding: 0 0 8px;
  min-height: 100%;
}

/* 顶部 Banner */
.home-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 18px 18px;
  background: linear-gradient(135deg, #C8763A 0%, #E8934D 60%, #F5B97A 100%);
  border-radius: 0 0 28px 28px;
  margin-bottom: 16px;
  box-shadow: 0 6px 20px rgba(200,118,58,.25);
}
.greeting {
  font-size: 22px;
  font-weight: 800;
  color: #fff;
  text-shadow: 0 1px 4px rgba(0,0,0,.15);
}
.date-text {
  font-size: 12px;
  color: rgba(255,255,255,.82);
  margin-top: 3px;
  font-weight: 500;
}
.app-logo {
  width: 68px;
  height: 68px;
  border-radius: 20px;
  object-fit: cover;
  box-shadow: 0 4px 16px rgba(0,0,0,.2);
  border: 3px solid rgba(255,255,255,.6);
  background: #fff;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 0 14px 14px;
}
.stat-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 16px 12px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(200,118,58,.08), 0 0 0 1px rgba(200,118,58,.05);
  text-decoration: none;
  color: var(--text);
  cursor: pointer;
  transition: transform .15s, box-shadow .15s;
}
.stat-card:active { transform: scale(.96); }
.stat-warn  { background: #FFFBEB; box-shadow: 0 2px 12px rgba(245,158,11,.15); }
.stat-danger { background: #FEF2F2; box-shadow: 0 2px 12px rgba(239,68,68,.15); }
.stat-icon { font-size: 22px; margin-bottom: 4px; }
.stat-num  { font-size: 32px; font-weight: 900; line-height: 1; }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; font-weight: 600; }

/* 分节标题 */
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 800;
  margin-bottom: 12px;
}
.section-title-row {
  padding: 0 14px;
  margin-bottom: 8px;
}
.section-title-text { font-size: 15px; font-weight: 800; color: var(--text); }
.see-all { font-size: 13px; color: var(--primary); text-decoration: none; font-weight: 700; }

/* 卡片内临期列表 */
.card { margin: 0 14px 14px; }
.alert-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1.5px dashed var(--border);
  cursor: pointer;
  transition: opacity .15s;
}
.alert-item:active { opacity: .7; }
.alert-item:last-child { border-bottom: none; }
.alert-info { display: flex; align-items: center; gap: 10px; }
.alert-icon { font-size: 26px; }
.alert-name { font-weight: 700; font-size: 14px; }
.alert-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

/* 快捷操作 */
.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  padding: 0 14px;
}
.quick-btn {
  border-radius: var(--radius);
  padding: 18px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text);
  font-weight: 700;
  box-shadow: 0 2px 10px rgba(0,0,0,.06);
  transition: transform .15s, box-shadow .15s;
}
.quick-btn:active { transform: scale(.94); box-shadow: 0 1px 5px rgba(0,0,0,.08); }
.quick-emoji { font-size: 30px; }
.quick-label { font-size: 12px; font-weight: 700; text-align: center; line-height: 1.3; }

/* 各色按钮 */
.quick-primary { background: linear-gradient(135deg, #FFF0E6, #FFE0C8); }
.quick-orange  { background: linear-gradient(135deg, #FFF3CD, #FFE8A3); }
.quick-green   { background: linear-gradient(135deg, #E8FDF0, #C8F5D8); }
.quick-blue    { background: linear-gradient(135deg, #E8F4FF, #C8E4FF); }
.quick-purple  { background: linear-gradient(135deg, #F0EEFF, #DDD8FF); }
.quick-gray    { background: linear-gradient(135deg, #F5F5F5, #EBEBEB); }
</style>
