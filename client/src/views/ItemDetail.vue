<template>
  <div class="page">
    <div class="page-header">
      <button class="back-btn" @click="$router.back()">←</button>
      <span class="page-title">{{ $t('itemDetail') }}</span>
      <div style="display:flex;gap:8px">
        <button class="btn btn-outline" style="padding:6px 12px;font-size:13px" @click="$router.push('/item/' + itemId + '/edit')">{{ $t('editBtn') }}</button>
        <button class="btn btn-danger" style="padding:6px 12px;font-size:13px" @click="deleteItem">{{ $t('delete') }}</button>
      </div>
    </div>

    <div v-if="item" class="detail-card">
      <!-- 商品图片 -->
      <div class="detail-image">
        <img v-if="item.image_path" :src="item.image_path" class="item-image" />
        <div v-else class="img-placeholder">{{ item.category_icon || '📦' }}</div>
      </div>

      <!-- 基本信息 -->
      <div class="detail-info">
        <h2 class="detail-name">{{ item.name }}</h2>
        <div class="detail-meta">
          <span class="badge badge-primary">{{ item.category_icon }} {{ item.category_name || $t('uncategorized') }}</span>
          <span class="badge" :class="item.total_stock <= item.min_stock ? 'badge-danger' : 'badge-success'">
            {{ $t('stockTotal') }} {{ item.total_stock }} {{ item.unit }}
          </span>
        </div>
        <div v-if="item.barcode" class="detail-barcode">条码: {{ item.barcode }}</div>
        <div v-if="item.notes" class="detail-notes">{{ item.notes }}</div>
      </div>

      <!-- 库存批次 -->
      <div class="inventory-section">
        <div class="section-header">
          <span class="section-title">{{ $t('stockBatch') }}</span>
          <button class="btn btn-primary" style="padding:6px 14px;font-size:13px" @click="showAddStock = true">{{ $t('addStockBtn') }}</button>
        </div>

        <div v-if="item.inventory && item.inventory.length > 0">
          <div v-for="inv in item.inventory" :key="inv.id" class="inventory-item">
            <div class="inv-info">
              <div class="inv-quantity">{{ inv.quantity }} {{ item.unit }}</div>
              <div class="inv-meta">
                <span v-if="inv.expiry_date" :class="['expiry-tag', getExpiryClass(inv.expiry_date)]">
                  {{ getExpiryText(inv.expiry_date) }}
                </span>
                <span v-if="inv.location">📍 {{ inv.location }}</span>
              </div>
            </div>
            <div class="inv-actions">
              <button class="action-btn" @click="consumeStock(inv)">{{ $t('consumeBtn') }}</button>
              <button class="action-btn delete" @click="deleteStock(inv.id)">{{ $t('delete') }}</button>
            </div>
          </div>
        </div>
        <div v-else class="empty-small">
          <span>{{ $t('noStock') }}</span>
        </div>
      </div>
    </div>

    <!-- 添加库存弹窗 -->
    <div v-if="showAddStock" class="modal-overlay" @click="showAddStock = false">
      <div class="modal-content" @click.stop>
        <h3>{{ $t('addStockTitle') }}</h3>
        <div class="form-group">
          <label class="form-label">{{ $t('quantity') }}</label>
          <input v-model.number="stockForm.quantity" type="number" class="form-input" :placeholder="$t('quantity')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('productionDate') }}</label>
          <input v-model="stockForm.production_date" type="date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('expiryDate') }}</label>
          <input v-model="stockForm.expiry_date" type="date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('location') }}</label>
          <input v-model="stockForm.location" class="form-input" :placeholder="$t('locationPlaceholder')" />
        </div>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showAddStock = false">{{ $t('cancel') }}</button>
          <button class="btn btn-primary" @click="submitAddStock" :disabled="!stockForm.quantity">{{ $t('confirm') }}</button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click="showDeleteConfirm = false">
      <div class="modal-content" @click.stop style="text-align:center;padding:24px 20px">
        <div style="font-size:48px;margin-bottom:12px">🗑️</div>
        <h3 style="margin-bottom:8px">确认删除</h3>
        <p style="color:var(--text-muted);margin-bottom:20px">确定删除「{{ item?.name }}」吗？<br/>所有库存记录也将一并删除，此操作不可撤销。</p>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDeleteItem" style="flex:1">确认删除</button>
        </div>
      </div>
    </div>

    <!-- 删除库存确认弹窗 -->
    <div v-if="showDeleteStockConfirm" class="modal-overlay" @click="showDeleteStockConfirm = false">
      <div class="modal-content" @click.stop style="text-align:center;padding:24px 20px">
        <div style="font-size:48px;margin-bottom:12px">🗑️</div>
        <h3 style="margin-bottom:8px">删除库存批次</h3>
        <p style="color:var(--text-muted);margin-bottom:20px">确定删除该库存批次吗？此操作不可撤销。</p>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showDeleteStockConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDeleteStock" style="flex:1">确认删除</button>
        </div>
      </div>
    </div>

    <!-- 消耗弹窗 -->
    <div v-if="showConsume" class="modal-overlay" @click="showConsume = false">
      <div class="modal-content" @click.stop>
        <h3>{{ $t('consumeTitle') }}</h3>
        <p style="color:var(--text-muted);margin-bottom:12px">{{ $t('consumeTitle') }}: {{ selectedStock?.quantity }} {{ item?.unit }}</p>
        <div class="form-group">
          <label class="form-label">{{ $t('consumeQuantity') }}</label>
          <input v-model.number="consumeForm.quantity" type="number" class="form-input" :placeholder="$t('consumeQuantity')" />
        </div>
        <div class="form-group">
          <label class="form-label">{{ $t('notes') }}</label>
          <input v-model="consumeForm.notes" class="form-input" :placeholder="$t('notesPlaceholder')" />
        </div>
        <div class="form-actions">
          <button class="btn btn-outline" @click="showConsume = false">{{ $t('cancel') }}</button>
          <button class="btn btn-primary" @click="submitConsume" :disabled="!consumeForm.quantity">{{ $t('confirmConsume') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const itemId = route.params.id

const item = ref(null)
const showAddStock = ref(false)
const showConsume = ref(false)
const showDeleteConfirm = ref(false)
const showDeleteStockConfirm = ref(false)
const deletingStockId = ref(null)
const selectedStock = ref(null)

const stockForm = ref({ quantity: 1, production_date: '', expiry_date: '', location: '', notes: '' })
const consumeForm = ref({ quantity: 1, notes: '' })

const loadItem = async () => {
  const res = await api.getItem(itemId)
  item.value = res.data
}

const getExpiryClass = (date) => {
  const days = Math.ceil((new Date(date) - new Date()) / (1000 * 60 * 60 * 24))
  if (days < 0) return 'expired'
  if (days <= 7) return 'warning'
  return 'normal'
}

const getExpiryText = (date) => {
  const days = Math.ceil((new Date(date) - new Date()) / (1000 * 60 * 60 * 24))
  if (days < 0) return `已过期 ${Math.abs(days)} 天`
  if (days === 0) return '今天到期'
  if (days <= 7) return `${days} 天后到期`
  return date
}

const submitAddStock = async () => {
  await api.addInventory({
    item_id: itemId,
    ...stockForm.value
  })
  showAddStock.value = false
  stockForm.value = { quantity: 1, production_date: '', expiry_date: '', location: '', notes: '' }
  loadItem()
}

const consumeStock = (inv) => {
  selectedStock.value = inv
  consumeForm.value = { quantity: 1, notes: '' }
  showConsume.value = true
}

const submitConsume = async () => {
  await api.consumeInventory(selectedStock.value.id, consumeForm.value.quantity, consumeForm.value.notes)
  showConsume.value = false
  loadItem()
}

const deleteStock = (id) => {
  deletingStockId.value = id
  showDeleteStockConfirm.value = true
}

const doDeleteStock = async () => {
  showDeleteStockConfirm.value = false
  try {
    await api.deleteInventory(deletingStockId.value)
    loadItem()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

const deleteItem = () => {
  showDeleteConfirm.value = true
}

const doDeleteItem = async () => {
  showDeleteConfirm.value = false
  try {
    await api.deleteItem(itemId)
    router.replace('/inventory')
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

onMounted(loadItem)
</script>

<style scoped>
.back-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 4px;
}

.detail-card { background: var(--card); border-radius: var(--radius); overflow: hidden; }
.detail-image {
  width: 100%;
  background: var(--primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.detail-image .item-image {
  width: 100%;
  max-width: 200px;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 16px;
}
.img-placeholder { font-size: 80px; }

.detail-info { padding: 16px; }
.detail-name { font-size: 20px; font-weight: 700; margin-bottom: 10px; }
.detail-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.detail-barcode { font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }
.detail-notes { font-size: 14px; color: var(--text-muted); padding: 10px; background: var(--bg); border-radius: 8px; }

.inventory-section { padding: 16px; border-top: 1px solid var(--border); }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-title { font-weight: 700; }

.inventory-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg);
  border-radius: 10px;
  margin-bottom: 8px;
}
.inv-quantity { font-weight: 700; font-size: 16px; }
.inv-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; display: flex; gap: 8px; }
.expiry-tag { padding: 2px 8px; border-radius: 99px; font-size: 11px; }
.expiry-tag.expired { background: var(--danger-light); color: var(--danger); }
.expiry-tag.warning { background: var(--warning-light); color: var(--warning); }
.expiry-tag.normal { background: var(--success-light); color: var(--success); }

.inv-actions { display: flex; gap: 8px; }
.action-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  background: var(--primary);
  color: #fff;
}
.action-btn.delete { background: var(--danger-light); color: var(--danger); }

.empty-small { text-align: center; padding: 20px; color: var(--text-muted); font-size: 14px; }

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
