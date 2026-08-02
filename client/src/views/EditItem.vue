<template>
  <div class="page">
    <div class="page-header">
      <button class="back-btn" @click="$router.back()">←</button>
      <span class="page-title">{{ $t('editItem') }}</span>
      <span></span>
    </div>

    <div v-if="item" class="edit-form">
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

      <button type="button" class="btn btn-primary btn-full" style="margin-top:20px;margin-bottom:calc(var(--nav-height) + var(--safe-bottom) + 16px)" :disabled="submitting" @click="submitForm">
        {{ submitting ? $t('saving') : $t('save') }}
      </button>
    </div>

    <div v-else class="empty">
      <div class="empty-icon">⏳</div>
      <div class="empty-text">{{ $t('loading') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/index.js'
import { t } from '../i18n/index.js'

const route = useRoute()
const router = useRouter()
const itemId = route.params.id

const item = ref(null)
const categories = ref([])
const previewImage = ref(null)
const imageFile = ref(null)
const submitting = ref(false)

const form = ref({
  name: '',
  barcode: '',
  category_id: '',
  unit: '个',
  min_stock: 1,
  notes: ''
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
      if (form.value[k] != null && form.value[k] !== '') formData.append(k, form.value[k])
    })
    if (imageFile.value) formData.append('image', imageFile.value)

    await api.updateItem(itemId, formData)
    alert('✅ ' + t('updateSuccess'))
    router.replace('/item/' + itemId)
  } catch (e) {
    alert('保存失败: ' + e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const [itemRes, catRes] = await Promise.all([
    api.getItem(itemId),
    api.getCategories()
  ])
  item.value = itemRes.data
  categories.value = catRes.data

  // 填充表单
  form.value = {
    name: item.value.name || '',
    barcode: item.value.barcode || '',
    category_id: item.value.category_id || '',
    unit: item.value.unit || '个',
    min_stock: item.value.min_stock || 1,
    notes: item.value.notes || ''
  }
  previewImage.value = item.value.image_path || null
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
</style>
