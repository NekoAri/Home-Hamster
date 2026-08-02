<template>
  <div class="lang-page">
    <div class="lang-card">
      <img src="/hamster-logo.jpg" class="lang-logo" alt="Home Hamster" />
      <h1 class="lang-title">Home Hamster 🐹</h1>
      <p class="lang-desc">{{ t('selectLanguageDesc') }}</p>

      <div class="lang-options">
        <button
          v-for="loc in availableLocales"
          :key="loc.code"
          class="lang-btn"
          :class="{ active: selected === loc.code }"
          @click="selected = loc.code"
        >
          <span class="lang-flag">{{ loc.code === 'zh-CN' ? '🇨🇳' : '🇺🇸' }}</span>
          <span class="lang-name">{{ loc.label }}</span>
          <span v-if="selected === loc.code" class="lang-check">✓</span>
        </button>
      </div>

      <button class="btn btn-primary btn-full" style="margin-top:32px;padding:15px;font-size:16px;border-radius:16px" @click="confirm">
        {{ t('confirm') }} ›
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { t, availableLocales, setLocale, isFirstVisit } from '../i18n/index.js'

const router = useRouter()
const selected = ref('zh-CN')

const confirm = () => {
  setLocale(selected.value)
  router.replace('/')
}
</script>

<style scoped>
.lang-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #C8763A 0%, #E8934D 60%, #F5B97A 100%);
}
.lang-card {
  background: #fff;
  border-radius: 28px;
  padding: 40px 28px;
  width: 100%;
  max-width: 360px;
  text-align: center;
  box-shadow: 0 24px 64px rgba(180,100,40,.25);
}
.lang-logo {
  width: 100px;
  height: 100px;
  border-radius: 24px;
  object-fit: cover;
  margin-bottom: 16px;
  box-shadow: 0 6px 20px rgba(200,118,58,.25);
  border: 3px solid rgba(200,118,58,.15);
}
.lang-title {
  font-size: 22px;
  font-weight: 800;
  margin-bottom: 8px;
  color: #3D2B1F;
}
.lang-desc {
  font-size: 14px;
  color: #9C7E6A;
  margin-bottom: 28px;
}
.lang-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lang-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  border: 2px solid #F0DDD0;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  font-size: 16px;
  transition: all .2s;
  width: 100%;
  text-align: left;
}
.lang-btn.active {
  border-color: #C8763A;
  background: #FFF3E8;
}
.lang-btn:active { transform: scale(.98); }
.lang-flag { font-size: 28px; }
.lang-name { flex: 1; font-weight: 700; color: #3D2B1F; }
.lang-check { color: #C8763A; font-weight: 800; font-size: 18px; }
</style>
