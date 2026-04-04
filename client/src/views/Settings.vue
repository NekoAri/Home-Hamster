<template>
  <div class="page">
    <div class="page-header">
      <span class="page-title">{{ $t('settings') }}</span>
    </div>

    <!-- 语言设置 -->
    <div class="card">
      <div class="setting-label">🌐 {{ $t('language') }}</div>
      <div class="setting-desc">{{ $t('languageDesc') }}</div>
      <div class="lang-options">
        <button
          v-for="loc in availableLocales"
          :key="loc.code"
          class="option-btn"
          :class="{ active: locale.value === loc.code }"
          @click="changeLang(loc.code)"
        >
          <span class="opt-icon">{{ loc.code === 'zh-CN' ? '🇨🇳' : '🇺🇸' }}</span>
          <span class="opt-name">{{ loc.label }}</span>
          <span v-if="locale.value === loc.code" class="opt-check">✓</span>
        </button>
      </div>
    </div>

    <!-- 主题颜色设置 -->
    <div class="card">
      <div class="setting-label">🎨 {{ $t('themeColor') }}</div>
      <div class="setting-desc">{{ $t('themeColorDesc') }}</div>

      <!-- 预设颜色 -->
      <div class="theme-label">{{ $t('themePreset') }}</div>
      <div class="theme-presets">
        <button
          v-for="preset in themePresets"
          :key="preset.value"
          class="preset-dot"
          :style="{ background: preset.value }"
          :class="{ active: currentTheme === preset.value }"
          :title="preset.label"
          @click="applyThemeColor(preset.value)"
        >
          <span v-if="currentTheme === preset.value" class="dot-check">✓</span>
        </button>
      </div>

      <!-- 自定义颜色 -->
      <div class="theme-label">{{ $t('themeCustom') }}</div>
      <div class="custom-color-row">
        <div class="color-preview" :style="{ background: currentTheme }"></div>
        <input
          type="color"
          class="color-picker"
          :value="currentTheme"
          @input="onCustomColor"
        />
        <span class="color-hex">{{ currentTheme }}</span>
        <button class="btn-reset" @click="applyThemeColor('#C8763A')" :title="'重置'">↺</button>
      </div>

      <div v-if="themeMsg" class="theme-msg">{{ themeMsg }}</div>
    </div>

    <!-- 数据库配置 -->
    <div class="card">
      <div class="setting-label">💾 {{ $t('dbConfig') }}</div>
      <div class="setting-desc">{{ $t('dbConfigDesc') }}</div>

      <div v-if="dbConfig" class="db-status">
        {{ $t('dbCurrentType', { type: dbConfig.type === 'sqlite' ? 'SQLite' : 'JSON' }) }}
      </div>

      <div class="db-type-options">
        <button
          class="option-btn"
          :class="{ active: dbForm.type === 'json' }"
          @click="dbForm.type = 'json'"
        >
          <span class="opt-icon">📄</span>
          <div class="db-type-info">
            <span class="opt-name">{{ $t('dbTypeJson') }}</span>
            <span class="db-type-desc">{{ $t('dbTypeJsonDesc') }}</span>
          </div>
          <span v-if="dbForm.type === 'json'" class="opt-check">✓</span>
        </button>
        <button
          class="option-btn"
          :class="{ active: dbForm.type === 'sqlite' }"
          @click="dbForm.type = 'sqlite'"
        >
          <span class="opt-icon">🗃️</span>
          <div class="db-type-info">
            <span class="opt-name">{{ $t('dbTypeSqlite') }}</span>
            <span class="db-type-desc">{{ $t('dbTypeSqliteDesc') }}</span>
          </div>
          <span v-if="dbForm.type === 'sqlite'" class="opt-check">✓</span>
        </button>
      </div>

      <!-- SQLite 配置表单 -->
      <div v-if="dbForm.type === 'sqlite'" class="db-form">
        <div class="form-group">
          <label class="form-label">{{ $t('dbPath') }}</label>
          <input v-model="dbForm.sqlitePath" class="form-input" :placeholder="$t('dbPathPlaceholder')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('dbPassword') }}</label>
          <input v-model="dbForm.sqlitePassword" type="password" class="form-input" :placeholder="$t('dbPasswordPlaceholder')" />
        </div>
        <button class="btn btn-outline" style="width:100%;margin-bottom:10px" @click="testConnection" :disabled="testing">
          {{ testing ? '...' : $t('dbTestConnection') }}
        </button>
      </div>

      <button class="btn btn-primary" style="width:100%" @click="saveDbConfig" :disabled="saving">
        {{ saving ? '...' : $t('dbSave') }}
      </button>

      <div v-if="dbMessage" class="db-message" :class="dbMessageType">
        {{ dbMessage }}
      </div>
    </div>

    <!-- 分类管理入口 -->
    <div class="card">
      <div class="setting-label">🏷️ {{ $t('categoryManage') }}</div>
      <router-link to="/categories" class="setting-link">
        <span>{{ $t('categoryManage') }}</span>
        <span class="arrow">›</span>
      </router-link>
    </div>

    <!-- 关于 -->
    <div class="card about-card">
      <img src="/hamster-logo.jpg" class="about-logo" alt="logo" />
      <div class="about-name">Home Hamster</div>
      <div class="about-ver">v1.0.0 🐹</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { locale, setLocale, availableLocales } from '../i18n/index.js'
import { api } from '../api/index.js'

const changeLang = (code) => {
  setLocale(code)
}

// ===== 主题颜色 =====
const THEME_KEY = 'app-theme-color'

const themePresets = [
  { label: '仓鼠棕 🐹', value: '#C8763A' },
  { label: 'Indigo', value: '#4F46E5' },
  { label: 'Violet', value: '#7C3AED' },
  { label: 'Pink', value: '#DB2777' },
  { label: 'Rose', value: '#E11D48' },
  { label: 'Orange', value: '#EA580C' },
  { label: 'Amber', value: '#D97706' },
  { label: 'Emerald', value: '#059669' },
  { label: 'Teal', value: '#0D9488' },
  { label: 'Cyan', value: '#0891B2' },
  { label: 'Blue', value: '#2563EB' },
  { label: 'Slate', value: '#475569' },
]

const currentTheme = ref(localStorage.getItem(THEME_KEY) || '#C8763A')
const themeMsg = ref('')

const applyThemeColor = (color) => {
  currentTheme.value = color
  const r = parseInt(color.slice(1,3), 16)
  const g = parseInt(color.slice(3,5), 16)
  const b = parseInt(color.slice(5,7), 16)
  document.documentElement.style.setProperty('--primary', color)
  document.documentElement.style.setProperty('--primary-light', `rgba(${r},${g},${b},0.12)`)
  document.documentElement.style.setProperty('--primary-rgb', `${r},${g},${b}`)
  localStorage.setItem(THEME_KEY, color)
  const metaTheme = document.querySelector('meta[name="theme-color"]')
  if (metaTheme) metaTheme.setAttribute('content', color)
  themeMsg.value = '✓ 主题已应用'
  setTimeout(() => { themeMsg.value = '' }, 1500)
}

let colorDebounce = null
const onCustomColor = (e) => {
  clearTimeout(colorDebounce)
  colorDebounce = setTimeout(() => applyThemeColor(e.target.value), 100)
}

// ===== 数据库配置 =====
const dbConfig = ref(null)
const dbForm = ref({ type: 'json', sqlitePath: '', sqlitePassword: '' })
const saving = ref(false)
const testing = ref(false)
const dbMessage = ref('')
const dbMessageType = ref('success')

const showDbMessage = (text, type = 'success') => {
  dbMessage.value = text
  dbMessageType.value = type
  setTimeout(() => { dbMessage.value = '' }, 3000)
}

const loadDbConfig = async () => {
  try {
    const res = await api.getDbConfig()
    dbConfig.value = res.data
    dbForm.value = {
      type: res.data.type || 'json',
      sqlitePath: res.data.sqlitePath || '',
      sqlitePassword: '',
    }
  } catch (e) {
    // ignore
  }
}

const testConnection = async () => {
  testing.value = true
  try {
    const res = await api.testDbConnection({
      type: dbForm.value.type,
      sqlitePath: dbForm.value.sqlitePath,
      sqlitePassword: dbForm.value.sqlitePassword,
    })
    if (res.success) {
      showDbMessage(res.message, 'success')
    } else {
      showDbMessage(res.message, 'error')
    }
  } catch (e) {
    showDbMessage(e.message, 'error')
  } finally {
    testing.value = false
  }
}

const saveDbConfig = async () => {
  saving.value = true
  try {
    const res = await api.saveDbConfig(dbForm.value)
    if (res.success) {
      showDbMessage(res.message, 'success')
      dbConfig.value = { ...dbForm.value, hasPassword: !!dbForm.value.sqlitePassword }
    } else {
      showDbMessage(res.message, 'error')
    }
  } catch (e) {
    showDbMessage(e.message, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(loadDbConfig)
</script>

<style scoped>
.setting-label {
  font-weight: 700;
  font-size: 15px;
  margin-bottom: 4px;
}
.setting-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 14px;
}

/* 通用选项按钮 */
.lang-options, .db-type-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 4px;
}
.option-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 2px solid var(--border);
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  font-size: 15px;
  transition: all .2s;
  width: 100%;
  text-align: left;
}
.option-btn.active {
  border-color: var(--primary);
  background: var(--primary-light);
}
.option-btn:active { transform: scale(.98); }
.opt-icon { font-size: 24px; flex-shrink: 0; }
.opt-name { flex: 1; font-weight: 600; text-align: left; }
.opt-check { color: var(--primary); font-weight: 700; font-size: 18px; }

/* 主题颜色 */
.theme-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  margin: 12px 0 8px;
}
.theme-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 4px;
}
.preset-dot {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: 3px solid transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform .15s, border-color .15s;
  position: relative;
}
.preset-dot.active {
  border-color: rgba(0,0,0,0.25);
  transform: scale(1.15);
}
.dot-check {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  text-shadow: 0 1px 3px rgba(0,0,0,0.5);
}
.custom-color-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  background: var(--bg);
  margin-bottom: 8px;
}
.color-preview {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 2px solid rgba(0,0,0,.1);
  flex-shrink: 0;
}
.color-picker {
  width: 36px;
  height: 36px;
  border: none;
  padding: 0;
  cursor: pointer;
  background: none;
  flex-shrink: 0;
}
.color-hex {
  flex: 1;
  font-family: monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.btn-reset {
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: 8px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-muted);
}
.theme-msg {
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
  padding: 6px 0 2px;
}

/* 数据库 */
.db-type-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.db-type-desc {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 400;
}
.db-status {
  display: inline-block;
  padding: 4px 12px;
  background: var(--bg);
  border-radius: 99px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 14px;
}
.db-form {
  margin-bottom: 14px;
}
.db-form .form-group {
  margin-bottom: 12px;
}
.db-form .form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-muted);
}
.db-form .form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  font-size: 14px;
  background: var(--bg);
  outline: none;
  transition: border-color .2s;
  box-sizing: border-box;
}
.db-form .form-input:focus {
  border-color: var(--primary);
}
.db-message {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}
.db-message.success {
  background: var(--success-light);
  color: var(--success);
}
.db-message.error {
  background: var(--danger-light);
  color: var(--danger);
}

/* 分类入口 */
.setting-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid var(--border);
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
}
.arrow { font-size: 20px; color: var(--text-muted); }

/* 关于 */
.about-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 16px;
}
.about-logo {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(79,70,229,.25);
  margin-bottom: 4px;
}
.about-name {
  font-weight: 700;
  font-size: 16px;
}
.about-ver {
  font-size: 13px;
  color: var(--text-muted);
}
</style>
