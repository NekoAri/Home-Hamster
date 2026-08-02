<template>
  <div class="page">
    <!-- 页头 -->
    <div class="page-header">
      <button class="back-btn" @click="$router.back()">‹</button>
      <span class="page-title">
        {{ activeTab === 'expiring' ? $t('expiringPageTitle') : $t('expiredPageTitle') }}
      </span>
      <span></span>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'expiring' }"
        @click="switchTab('expiring')"
      >
        ⚠️ {{ $t('expiringTab') }}
        <span v-if="expiringItems.length" class="tab-badge tab-badge-warn">{{ expiringItems.length }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'expired' }"
        @click="switchTab('expired')"
      >
        🔴 {{ $t('expiredTab') }}
        <span v-if="expiredItems.length" class="tab-badge tab-badge-danger">{{ expiredItems.length }}</span>
      </button>
    </div>

    <!-- 临期物品列表 -->
    <div v-show="activeTab === 'expiring'">
      <div v-if="loading" class="loading-wrap">
        <div class="loading-spin"></div>
      </div>
      <template v-else-if="expiringItems.length > 0">
        <div
          v-for="item in expiringItems"
          :key="item.inv_id"
          class="item-card"
          @click="$router.push('/item/' + item.item_id)"
        >
          <div class="item-icon">{{ item.category_icon || '📦' }}</div>
          <div class="item-info">
            <div class="item-name">{{ item.name }}</div>
            <div class="item-meta">
              <span>{{ item.expiry_date }}</span>
              <span class="dot">·</span>
              <span>{{ $t('expiryInfo', { date: item.expiry_date, qty: item.quantity, unit: item.unit }).split(' · ').slice(1).join(' · ') }}</span>
            </div>
            <div class="item-category">{{ item.category_name || '' }}</div>
          </div>
          <span class="badge badge-warning">
            {{ $t('daysText', { days: item.days_left }) }}
          </span>
        </div>
      </template>
      <div v-else class="empty">
        <div class="empty-icon">✅</div>
        <div class="empty-text">{{ $t('noExpiringItems') }}</div>
      </div>
    </div>

    <!-- 已过期物品列表 -->
    <div v-show="activeTab === 'expired'">
      <div v-if="loading" class="loading-wrap">
        <div class="loading-spin"></div>
      </div>
      <template v-else-if="expiredItems.length > 0">
        <div
          v-for="item in expiredItems"
          :key="item.inv_id"
          class="item-card"
          @click="$router.push('/item/' + item.item_id)"
        >
          <div class="item-icon">{{ item.category_icon || '📦' }}</div>
          <div class="item-info">
            <div class="item-name">{{ item.name }}</div>
            <div class="item-meta">
              <span>{{ item.expiry_date }}</span>
              <span class="dot">·</span>
              <span>剩余 {{ item.quantity }}{{ item.unit }}</span>
            </div>
            <div class="item-category">{{ item.category_name || '' }}</div>
          </div>
          <span class="badge badge-danger">{{ $t('expired') }}</span>
        </div>
      </template>
      <div v-else class="empty">
        <div class="empty-icon">✅</div>
        <div class="empty-text">{{ $t('noExpiredItems') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/index.js'

const route = useRoute()
const loading = ref(true)

// 根据来源 tab 参数决定初始 tab
const activeTab = ref(route.query.tab === 'expired' ? 'expired' : 'expiring')

const allItems = ref([])
const expiringItems = ref([])  // days_left > 0
const expiredItems = ref([])   // days_left <= 0

const switchTab = (tab) => {
  activeTab.value = tab
}

onMounted(async () => {
  try {
    // 获取 60 天内临期（包含已过期的 days_left < 0）
    const [expRes] = await Promise.all([
      api.getExpiring(60),
    ])
    allItems.value = expRes.data || []
    // 分类
    expiringItems.value = allItems.value.filter(i => i.days_left > 0)
    expiredItems.value  = allItems.value.filter(i => i.days_left <= 0)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.back-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--text);
  padding: 0 4px;
  line-height: 1;
}
.page-title { font-size: 20px; font-weight: 700; }

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  background: var(--bg);
  border-radius: 12px;
  padding: 4px;
  border: 1.5px solid var(--border);
}
.tab-btn {
  flex: 1;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: var(--text-muted);
  transition: all .2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.tab-btn.active {
  background: var(--card);
  color: var(--text);
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
}
.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 700;
}
.tab-badge-warn { background: var(--warning-light); color: var(--warning); }
.tab-badge-danger { background: var(--danger-light); color: var(--danger); }

/* Item card */
.item-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  cursor: pointer;
  transition: transform .1s;
}
.item-card:active { transform: scale(.98); }
.item-icon { font-size: 32px; flex-shrink: 0; }
.item-info { flex: 1; min-width: 0; }
.item-name { font-weight: 700; font-size: 15px; margin-bottom: 3px; }
.item-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.dot { color: var(--border); }
.item-category {
  font-size: 11px;
  color: var(--primary);
  margin-top: 3px;
  font-weight: 500;
}

/* Loading */
.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}
.loading-spin {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty */
.empty {
  text-align: center;
  padding: 60px 24px;
  color: var(--text-muted);
}
.empty-icon { font-size: 52px; margin-bottom: 12px; }
.empty-text { font-size: 15px; }
</style>
