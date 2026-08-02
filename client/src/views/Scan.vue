<template>
  <div class="page scan-page">
    <div class="scan-header">
      <button class="back-btn" @click="$router.back()">←</button>
      <span class="page-title">{{ isConsumeMode ? $t('scanToConsume') : $t('scanToStock') }}</span>
      <span></span>
    </div>

    <!-- 扫码区域 -->
    <div class="scan-container">
      <div v-if="!cameraActive" class="camera-placeholder">
        <div class="camera-icon">📷</div>
        <p class="camera-tip">{{ $t('scanHint') }}</p>
        <button class="btn btn-primary" @click="startCamera">{{ $t('startCamera') }}</button>
      </div>
      <div v-else id="reader" class="reader-container"></div>
    </div>

    <!-- 手动输入条码 -->
    <div class="manual-input">
      <input v-model="manualBarcode" class="form-input" :placeholder="$t('manualInputPlaceholder')" />
      <button class="btn btn-primary" @click="searchByBarcode" :disabled="!manualBarcode">{{ $t('search') }}</button>
    </div>

    <!-- 扫码结果 -->
    <div v-if="scanResult" class="scan-result">
      <div v-if="scanResult.found" class="result-card">
        <div class="result-title">✅ {{ $t('foundItem') }}</div>
        <div class="result-item">
          <span class="result-icon">{{ scanResult.data.category_icon || '📦' }}</span>
          <div>
            <div class="result-name">{{ scanResult.data.name }}</div>
            <div class="result-meta">{{ $t('currentStock') }}: {{ scanResult.data.total_stock }} {{ scanResult.data.unit }}</div>
          </div>
        </div>
        <button v-if="!isConsumeMode" class="btn btn-primary btn-full" style="margin-bottom:8px" @click="addStock">{{ $t('addStock') }}</button>
        <button class="btn btn-primary btn-full" :class="{ 'btn-outline': !isConsumeMode }" @click="consumeStock" :disabled="!isConsumeMode && selectedItem.total_stock <= 0">{{ $t('consumeStock') }}</button>
      </div>

      <div v-else class="result-card">
        <div class="result-title">🆕 {{ $t('createNew') }}</div>
        <p class="result-desc">{{ $t('notFound') }} ({{ scanResult.barcode }})</p>
        <button class="btn btn-primary btn-full" @click="createNewItem">{{ $t('createNew') }}</button>
      </div>
    </div>

    <!-- 添加库存弹窗 -->
    <div v-if="showAddForm" class="modal-overlay" @click="showAddForm = false">
      <div class="modal-content" @click.stop>
        <h3>{{ $t('addStockTitle') }} - {{ selectedItem?.name }}</h3>
        <div class="form-group">
          <label class="form-label">{{ $t('quantity') }}</label>
          <input v-model.number="form.quantity" type="number" class="form-input" :placeholder="$t('quantity')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('productionDate') }}</label>
          <input v-model="form.production_date" type="date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('expiryDate') }}</label>
          <input v-model="form.expiry_date" type="date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('location') }}</label>
          <input v-model="form.location" class="form-input" :placeholder="$t('locationPlaceholder')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('notes') }}</label>
          <input v-model="form.notes" class="form-input" :placeholder="$t('notesPlaceholder')" />
        </div>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showAddForm = false">{{ $t('cancel') }}</button>
          <button class="btn btn-primary" @click="submitAddStock" :disabled="!form.quantity">{{ $t('confirmAdd') }}</button>
        </div>
      </div>
    </div>

    <!-- 消耗库存弹窗 -->
    <div v-if="showConsumeForm" class="modal-overlay" @click="showConsumeForm = false">
      <div class="modal-content" @click.stop>
        <h3>{{ $t('consumeTitle') }} - {{ selectedItem?.name }}</h3>
        <p style="color:var(--text-muted);margin-bottom:12px">{{ $t('currentStock') }}: {{ selectedItem?.total_stock }} {{ selectedItem?.unit }}</p>
        <div class="form-group">
          <label class="form-label">{{ $t('consumeQuantity') }}</label>
          <input v-model.number="consumeForm.quantity" type="number" class="form-input" :placeholder="$t('consumeQuantity')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('notes') }}</label>
          <input v-model="consumeForm.notes" class="form-input" :placeholder="$t('notesPlaceholder')" />
        </div>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showConsumeForm = false">{{ $t('cancel') }}</button>
          <button class="btn btn-primary" @click="submitConsume" :disabled="!consumeForm.quantity">{{ $t('confirmConsume') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '../api/index.js'
import { t } from '../i18n/index.js'

const router = useRouter()
const route = useRoute()
const isConsumeMode = ref(route.query.mode === 'consume')
const manualBarcode = ref('')
const scanResult = ref(null)
const showAddForm = ref(false)
const selectedItem = ref(null)
const form = ref({ quantity: 1, production_date: '', expiry_date: '', location: '', notes: '' })
const consumeForm = ref({ quantity: 1, notes: '' })
const showConsumeForm = ref(false)
const cameraActive = ref(false)
const scanError = ref('')

let html5QrCode = null

// 页面加载时自动启动摄像头
onMounted(() => {
  startCamera()
})

// 启动摄像头扫码
const startCamera = async () => {
  scanError.value = ''
  try {
    // 先检查浏览器支持
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('浏览器不支持摄像头访问')
    }

    // 检查是否有可用摄像头
    const devices = await navigator.mediaDevices.enumerateDevices()
    const videoDevices = devices.filter(d => d.kind === 'videoinput')
    console.log('可用摄像头:', videoDevices)
    
    if (videoDevices.length === 0) {
      throw new Error('未检测到摄像头设备')
    }

    // 先请求摄像头权限
    let stream = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    } catch (permErr) {
      // 后置摄像头失败，改用任意摄像头
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true })
      } catch (e) {
        throw new Error('摄像头权限被拒绝，请在设置中允许访问摄像头')
      }
    }
    // 立即释放这条 stream（html5-qrcode 会自己重新开启）
    stream.getTracks().forEach(t => t.stop())

    // 关键：先让 #reader DOM 节点渲染出来
    cameraActive.value = true
    await nextTick()

    // 动态导入 html5-qrcode
    const { Html5Qrcode } = await import('html5-qrcode')
    
    html5QrCode = new Html5Qrcode('reader')
    
    const config = {
      fps: 10,
      qrbox: { width: 250, height: 250 },
      aspectRatio: 1.0
    }

    try {
      await html5QrCode.start(
        { facingMode: 'environment' },
        config,
        (decodedText) => {
          console.log('扫码成功:', decodedText)
          manualBarcode.value = decodedText
          stopCamera()
          searchByBarcode()
        },
        () => { /* 持续扫描中，忽略帧错误 */ }
      )
    } catch (startErr) {
      // 后置摄像头失败，换前置
      await html5QrCode.start(
        { facingMode: 'user' },
        config,
        (decodedText) => {
          console.log('扫码成功:', decodedText)
          manualBarcode.value = decodedText
          stopCamera()
          searchByBarcode()
        },
        () => {}
      )
    }
  } catch (err) {
    console.error('摄像头启动失败:', err)
    let errorMsg = '无法启动摄像头'
    
    if (err.message.includes('Permission denied') || err.message.includes('权限')) {
      errorMsg = '摄像头权限被拒绝。\n\n请检查：\n1. 系统设置 > Safari > 相机 > 允许\n2. 地址栏左侧的相机图标 > 允许'
    } else if (err.message.includes('not supported') || err.message.includes('不支持')) {
      errorMsg = '当前浏览器不支持摄像头功能，请使用 Safari、Chrome 或 Edge 浏览器'
    } else if (err.message.includes('HTTPS') || err.message.includes('secure')) {
      errorMsg = '摄像头需要在 HTTPS 或 localhost 环境下使用。\n\n建议：\n1. 使用 http://localhost:3000 访问\n2. 或在 Mac mini 上配置 HTTPS'
    } else if (err.message.includes('未检测到摄像头') || err.message.includes('NotFound')) {
      errorMsg = '未检测到摄像头设备。\n\n可能原因：\n1. 电脑没有连接摄像头\n2. 摄像头被其他应用占用\n3. 虚拟机/远程桌面环境不支持摄像头\n\n建议：使用手动输入条码功能'
    } else if (err.name === 'NotAllowedError') {
      errorMsg = '摄像头权限被拒绝。请在 Safari 设置中允许相机访问。'
    } else if (err.name === 'NotFoundError') {
      errorMsg = '未找到摄像头设备'
    } else {
      errorMsg = `启动失败: ${err.message || err.name || '未知错误'}`
    }
    
    scanError.value = errorMsg
    alert(errorMsg)
  }
}

// 停止摄像头
const stopCamera = async () => {
  if (html5QrCode) {
    try {
      await html5QrCode.stop()
      await html5QrCode.clear()
    } catch (e) {
      console.log('停止摄像头:', e)
    }
    html5QrCode = null
  }
  cameraActive.value = false
}

onUnmounted(() => {
  stopCamera()
})

const searchByBarcode = async () => {
  if (!manualBarcode.value) return
  try {
    const res = await api.getItemByBarcode(manualBarcode.value)
    scanResult.value = { found: true, data: res.data, barcode: manualBarcode.value }
    selectedItem.value = res.data
    // 出库模式下自动弹出消耗弹窗
    if (isConsumeMode.value) consumeStock()
  } catch (e) {
    scanResult.value = { found: false, barcode: manualBarcode.value }
  }
}

const addStock = () => {
  form.value = { quantity: 1, production_date: '', expiry_date: '', location: '', notes: '' }
  showAddForm.value = true
}

const createNewItem = () => {
  router.push(`/add-item?barcode=${scanResult.value.barcode}`)
}

const consumeStock = () => {
  consumeForm.value = { quantity: 1, notes: '' }
  showConsumeForm.value = true
}

const submitConsume = async () => {
  if (!consumeForm.value.quantity || consumeForm.value.quantity <= 0) return
  try {
    // 获取该商品最近的库存批次来消耗
    const res = await api.getItem(selectedItem.value.id)
    const inventory = res.data.inventory || []
    if (inventory.length === 0) return alert(t('noStock'))

    // 消耗最早的批次
    const batch = inventory[0]
    const qty = Math.min(consumeForm.value.quantity, batch.quantity)
    await api.consumeInventory(batch.id, qty, consumeForm.value.notes)

    // 如果消耗数量超过当前批次，继续消耗下一批次
    let remaining = consumeForm.value.quantity - qty
    for (let i = 1; remaining > 0 && i < inventory.length; i++) {
      const b = inventory[i]
      const q = Math.min(remaining, b.quantity)
      await api.consumeInventory(b.id, q, consumeForm.value.notes)
      remaining -= q
    }

    alert(t('consumeSuccess'))
    showConsumeForm.value = false
    scanResult.value = null
    manualBarcode.value = ''
  } catch (e) {
    alert(t('consumeFailed') + ': ' + e.message)
  }
}

const submitAddStock = async () => {
  await api.addInventory({
    item_id: selectedItem.value.id,
    ...form.value
  })
  alert('✅ 库存添加成功！')
  showAddForm.value = false
  scanResult.value = null
  manualBarcode.value = ''
}
</script>

<style scoped>
.scan-page { padding-top: 8px; }
.scan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.back-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 4px;
}

.scan-container {
  background: #000;
  border-radius: var(--radius);
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  overflow: hidden;
}
.camera-placeholder {
  text-align: center;
  padding: 40px 20px;
}
.camera-icon {
  font-size: 64px;
  margin-bottom: 16px;
}
.camera-tip {
  color: rgba(255,255,255,0.7);
  font-size: 14px;
  margin-bottom: 20px;
}
.reader-container {
  width: 100%;
  min-height: 300px;
}
.reader-container :deep(video) {
  width: 100% !important;
  height: auto !important;
  border-radius: var(--radius);
}

.manual-input {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.manual-input .form-input { flex: 1; }
.manual-input .btn { padding: 11px 20px; }

.scan-result { margin-top: 8px; }
.result-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.result-title { font-weight: 700; margin-bottom: 12px; }
.result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--primary-light);
  border-radius: 10px;
  margin-bottom: 16px;
}
.result-icon { font-size: 32px; }
.result-name { font-weight: 700; }
.result-meta { font-size: 13px; color: var(--text-muted); }
.result-desc { color: var(--text-muted); margin-bottom: 16px; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 200;
}
.modal-content {
  background: var(--card);
  width: 100%;
  max-height: 80vh;
  border-radius: 20px 20px 0 0;
  padding: 20px;
  overflow-y: auto;
}
.modal-content h3 { margin-bottom: 16px; }
.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}
.form-actions .btn { flex: 1; }
</style>
