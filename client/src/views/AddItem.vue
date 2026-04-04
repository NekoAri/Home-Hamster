<template>
  <div class="page">
    <div class="page-header">
      <button class="back-btn" @click="$router.back()">←</button>
      <span class="page-title">{{ $t('addItem') }}</span>
      <span></span>
    </div>

    <form @submit.prevent="submitForm" class="add-form">
      <!-- 图片上传 -->
      <div class="form-group">
        <label class="form-label">{{ $t('itemName') }}</label>
        <div class="image-upload" @click="$refs.fileInput.click()">
          <img v-if="previewImage" :src="previewImage" class="preview-img" />
          <div v-else class="upload-placeholder">
            <span>📷</span>
            <span>{{ $t('uploadImage') }}</span>
          </div>
          <input ref="fileInput" type="file" accept="image/*" @change="handleImageChange" hidden />
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">{{ $t('itemName') }} *</label>
        <input v-model="form.name" class="form-input" :placeholder="$t('itemNamePlaceholder')" required />
      </div>

      <div class="form-group">
        <label class="form-label">{{ $t('barcode') }}</label>
        <input v-model="form.barcode" class="form-input" :placeholder="$t('barcodePlaceholder')" />
      </div>

      <div class="form-group">
        <label class="form-label">{{ $t('category') }}</label>
        <select v-model="form.category_id" class="form-select">
          <option value="">{{ $t('selectCategory') }}</option>
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.icon }} {{ cat.name }}</option>
        </select>
      </div>

      <div class="form-row">
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('unit') }}</label>
          <input v-model="form.unit" class="form-input" :placeholder="$t('unitPlaceholder')" />
        </div>
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('minStock') }}</label>
          <input v-model.number="form.min_stock" type="number" class="form-input" :placeholder="$t('minStockPlaceholder')" />
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">{{ $t('notes') }}</label>
        <textarea v-model="form.notes" class="form-textarea" :placeholder="$t('notesPlaceholder')"></textarea>
      </div>

      <!-- 初始库存（可选） -->
      <div class="section-title">{{ $t('initialStock') }}</div>
      <div class="form-row">
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('quantity') }}</label>
          <input v-model.number="initialStock.quantity" type="number" class="form-input" placeholder="0" />
        </div>
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('expiryDate') }}</label>
          <input v-model="initialStock.expiry_date" type="date" class="form-input" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('productionDate') }}</label>
          <input v-model="initialStock.production_date" type="date" class="form-input" />
        </div>
        <div class="form-group" style="flex:1">
          <label class="form-label">{{ $t('location') }}</label>
          <input v-model="initialStock.location" class="form-input" :placeholder="$t('locationPlaceholder')" />
        </div>
      </div>

      <button type="submit" class="btn btn-primary btn-full" style="margin-top:20px;margin-bottom:calc(var(--nav-height) + var(--safe-bottom) + 16px)" :disabled="submitting">
        {{ submitting ? $t('saving') : $t('saveItem') }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'
import { t } from '../i18n/index.js'

const route = useRoute()
const router = useRouter()

const categories = ref([])
const previewImage = ref(null)
const imageFile = ref(null)
const submitting = ref(false)

const form = ref({
  name: '',
  barcode: route.query.barcode || '',
  category_id: '',
  unit: t('defaultUnit'),
  min_stock: 1,
  notes: ''
})

const initialStock = ref({
  quantity: null,
  expiry_date: '',
  production_date: '',
  location: ''
})

const handleImageChange = (e) => {
  const file = e.target.files[0]
  if (!file) return
  imageFile.value = file
  previewImage.value = URL.createObjectURL(file)
}

const submitForm = async () => {
  if (!form.value.name) return alert(t('nameRequired'))
  
  submitting.value = true
  try {
    const formData = new FormData()
    Object.keys(form.value).forEach(k => {
      if (form.value[k] != null) formData.append(k, form.value[k])
    })
    if (imageFile.value) formData.append('image', imageFile.value)

    const res = await api.createItem(formData)
    const itemId = res.data.id

    // 如果有初始库存，添加库存记录
    if (initialStock.value.quantity && initialStock.value.quantity > 0) {
      await api.addInventory({
        item_id: itemId,
        quantity: initialStock.value.quantity,
        expiry_date: initialStock.value.expiry_date || null,
        production_date: initialStock.value.production_date || null,
        location: initialStock.value.location || '默认位置'
      })
    }

    alert('✅ 商品添加成功！')
    router.push('/item/' + itemId)
  } catch (e) {
    alert('保存失败: ' + e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const res = await api.getCategories()
  categories.value = res.data
})
</script>

<style scoped>
.back-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 4px;
}

.image-upload {
  width: 100%;
  height: 180px;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
}
.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}
.upload-placeholder span:first-child { font-size: 40px; }
.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.form-row {
  display: flex;
  gap: 12px;
}

.section-title {
  font-weight: 700;
  margin: 20px 0 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
</style>
