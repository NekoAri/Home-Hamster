<template>
  <div id="app-shell">
    <!-- 有新版本时显示更新提示条 -->
    <div v-if="needRefresh" class="update-bar">
      <span>{{ $t('updateAvailable') }}</span>
      <button class="update-btn" @click="updateApp">{{ $t('updateNow') }}</button>
      <button class="update-close" @click="needRefresh = false">&times;</button>
    </div>

    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>

    <!-- 底部导航栏 -->
    <nav v-if="showNav" class="bottom-nav">
      <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
        <span class="nav-icon">🏠</span>
        <span class="nav-label">{{ $t('navHome') }}</span>
      </router-link>
      <router-link to="/inventory" class="nav-item" :class="{ active: $route.path === '/inventory' }">
        <span class="nav-icon">📦</span>
        <span class="nav-label">{{ $t('navInventory') }}</span>
      </router-link>
      <router-link to="/scan" class="nav-item nav-scan">
        <span class="scan-btn">📷</span>
      </router-link>
      <router-link to="/stats" class="nav-item" :class="{ active: $route.path === '/stats' }">
        <span class="nav-icon">📊</span>
        <span class="nav-label">{{ $t('navStats') }}</span>
      </router-link>
      <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
        <span class="nav-icon">⚙️</span>
        <span class="nav-label">{{ $t('settings') }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide } from 'vue'
import { useRouter } from 'vue-router'
import { t as i18nT, locale, isFirstVisit } from './i18n/index.js'

const router = useRouter()

// 将 t 函数提供给所有子组件
provide('t', i18nT)

const needRefresh = ref(false)
let updateSW = null
const showNav = computed(() => !router.currentRoute.value.meta.hideNav)

// ===== 主题色应用 =====
const THEME_KEY = 'app-theme-color'
const applyTheme = (color) => {
  if (!color) return
  // 计算 light 版本（20% 不透明度）
  const r = parseInt(color.slice(1,3), 16)
  const g = parseInt(color.slice(3,5), 16)
  const b = parseInt(color.slice(5,7), 16)
  document.documentElement.style.setProperty('--primary', color)
  document.documentElement.style.setProperty('--primary-light', `rgba(${r},${g},${b},0.12)`)
  document.documentElement.style.setProperty('--primary-rgb', `${r},${g},${b}`)
  // 更新 PWA theme-color
  const metaTheme = document.querySelector('meta[name="theme-color"]')
  if (metaTheme) metaTheme.setAttribute('content', color)
}

// 首次访问检测
const needSetup = ref(false)
onMounted(async () => {
  // 应用保存的主题色
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme) applyTheme(savedTheme)
  else applyTheme('#C8763A') // 默认橙棕仓鼠色

  // 首次访问，跳转语言选择
  if (isFirstVisit() && router.currentRoute.value.path !== '/setup-language') {
    router.replace('/setup-language')
    return
  }

  // Service Worker 注册
  if ('serviceWorker' in navigator) {
    const { registerSW } = await import('virtual:pwa-register')
    updateSW = registerSW({
      onNeedRefresh() {
        needRefresh.value = true
      },
      onOfflineReady() {},
      onRegistered(swRegistration) {
        if (swRegistration) {
          setInterval(() => swRegistration.update(), 60 * 1000)
        }
      }
    })
  }
})

const updateApp = () => {
  if (updateSW) updateSW(true)
}
</script>

<style>
/* ===== 全局重置 ===== */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

:root {
  /* 主题色（可被 localStorage 覆盖） */
  --primary: #C8763A;
  --primary-light: #FFF3E8;
  --primary-rgb: 200,118,58;
  /* 功能色 */
  --danger: #EF4444;
  --danger-light: #FEF2F2;
  --warning: #F59E0B;
  --warning-light: #FFFBEB;
  --success: #10B981;
  --success-light: #ECFDF5;
  /* 文字 */
  --text: #3D2B1F;
  --text-muted: #9C7E6A;
  /* 边框 & 背景 */
  --border: #F0DDD0;
  --bg: #FDF8F5;
  --card: #FFFFFF;
  /* 圆角 — 更大更可爱 */
  --radius: 18px;
  --radius-sm: 12px;
  --nav-height: 68px;
  --safe-bottom: env(safe-area-inset-bottom, 0px);
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif;
  font-size: 15px;
  background: var(--bg);
  color: var(--text);
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

#app-shell {
  min-height: 100vh;
  padding-bottom: calc(var(--nav-height) + var(--safe-bottom));
}

/* ===== 底部导航 ===== */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0; right: 0;
  height: calc(var(--nav-height) + var(--safe-bottom));
  padding-bottom: var(--safe-bottom);
  background: rgba(255,255,255,0.92);
  border-top: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  z-index: 100;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  /* 顶部圆角营造浮起感 */
  border-radius: 22px 22px 0 0;
  box-shadow: 0 -4px 20px rgba(200,118,58,.10);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  text-decoration: none;
  color: var(--text-muted);
  padding: 6px 0 2px;
  transition: color .2s, transform .15s;
}
.nav-item.active { color: var(--primary); }
.nav-item.active .nav-icon { transform: scale(1.15); }
.nav-icon { font-size: 22px; line-height: 1; transition: transform .15s; }
.nav-label { font-size: 11px; font-weight: 600; }

.nav-scan { flex: 1.3; }
.scan-btn {
  width: 56px; height: 56px;
  background: linear-gradient(135deg, var(--primary) 0%, #E8934D 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  box-shadow: 0 6px 18px rgba(200,118,58,.45);
  margin-top: -20px;
  transition: transform .15s, box-shadow .15s;
}
.scan-btn:active { transform: scale(.93); box-shadow: 0 3px 10px rgba(200,118,58,.4); }

/* ===== 页面容器 ===== */
.page { padding: 16px 16px 8px; min-height: 100%; }
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; font-weight: 800; color: var(--text); }

/* ===== 卡片 ===== */
.card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 16px;
  /* 更柔和的阴影 + 细边框 */
  box-shadow: 0 2px 12px rgba(200,118,58,.08), 0 0 0 1px rgba(200,118,58,.05);
  margin-bottom: 14px;
}

/* ===== 徽章 ===== */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 700;
}
.badge-danger  { background: var(--danger-light);  color: var(--danger); }
.badge-warning { background: var(--warning-light); color: var(--warning); }
.badge-success { background: var(--success-light); color: var(--success); }
.badge-primary { background: var(--primary-light); color: var(--primary); }

/* ===== 按钮 ===== */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 22px;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  transition: opacity .15s, transform .1s, box-shadow .15s;
}
.btn:active { transform: scale(.96); opacity: .9; }
.btn-primary {
  background: linear-gradient(135deg, var(--primary) 0%, #E8934D 100%);
  color: #fff;
  box-shadow: 0 4px 14px rgba(200,118,58,.35);
}
.btn-primary:hover { box-shadow: 0 6px 18px rgba(200,118,58,.45); }
.btn-danger   { background: var(--danger);   color: #fff; }
.btn-outline  { background: transparent; border: 2px solid var(--border); color: var(--text); }
.btn-full { width: 100%; }

/* ===== 表单 ===== */
.form-group { margin-bottom: 14px; }
.form-label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; }
.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 15px;
  background: #fff;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
  appearance: none;
  color: var(--text);
}
.form-input:focus, .form-select:focus, .form-textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(200,118,58,.12);
}
.form-textarea { resize: vertical; min-height: 80px; }

/* ===== 过渡动画 ===== */
.fade-enter-active, .fade-leave-active { transition: opacity .15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ===== 空状态 ===== */
.empty {
  text-align: center;
  padding: 52px 24px;
  color: var(--text-muted);
}
.empty-icon { font-size: 56px; margin-bottom: 14px; }
.empty-text { font-size: 15px; font-weight: 500; }

/* ===== 更新提示条 ===== */
.update-bar {
  position: fixed;
  top: 0;
  left: 0; right: 0;
  background: linear-gradient(135deg, var(--primary) 0%, #E8934D 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  z-index: 300;
  box-shadow: 0 2px 12px rgba(200,118,58,.35);
}
.update-btn {
  background: #fff;
  color: var(--primary);
  border: none;
  border-radius: 8px;
  padding: 4px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.update-close {
  background: none;
  border: none;
  color: rgba(255,255,255,.75);
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
</style>
