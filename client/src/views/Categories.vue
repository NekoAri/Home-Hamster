<template>
  <div class="page">
    <div class="page-header">
      <span class="page-title">{{ $t('categoryManage') }}</span>
      <button class="btn-add" @click="openAdd">＋ {{ $t('addCategory') }}</button>
    </div>

    <!-- 分类列表 -->
    <div v-if="categories.length > 0" class="cat-list">
      <div v-for="cat in categories" :key="cat.id" class="cat-card">
        <div class="cat-main">
          <span class="cat-emoji">{{ cat.icon }}</span>
          <div class="cat-text">
            <div class="cat-name">{{ cat.name }}</div>
            <div class="cat-count">{{ cat.item_count ?? 0 }} 种商品</div>
          </div>
        </div>
        <div class="cat-actions">
          <button class="btn-icon btn-edit" @click="openEdit(cat)" title="编辑">✏️</button>
          <button class="btn-icon btn-del" @click="confirmDelete(cat)" title="删除">🗑️</button>
        </div>
      </div>
    </div>
    <div v-else class="empty">{{ $t('noCategories') }}</div>

    <!-- 新建 / 编辑弹窗 -->
    <div v-if="showModal" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <div class="modal-title">{{ editTarget ? $t('editCategory') : $t('addCategory') }}</div>

        <!-- Emoji 选择 -->
        <div class="emoji-picker">
          <div
            v-for="e in emojiList" :key="e"
            class="emoji-opt" :class="{ active: form.icon === e }"
            @click="form.icon = e"
          >{{ e }}</div>
        </div>

        <input
          v-model="form.name"
          class="input"
          :placeholder="$t('categoryNamePlaceholder')"
          maxlength="20"
          @keyup.enter="save"
        />

        <div class="modal-btns">
          <button class="btn-cancel" @click="closeModal">{{ $t('cancel') }}</button>
          <button class="btn-save" :disabled="!form.name.trim()" @click="save">
            {{ saving ? $t('saving') : $t('save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-mask" @click.self="deleteTarget = null">
      <div class="modal">
        <div class="modal-title">{{ $t('deleteConfirm') }}</div>
        <p class="del-tip">
          删除「{{ deleteTarget.name }}」分类？<br>
          <span v-if="deleteTarget.item_count > 0" class="warn-text">
            ⚠️ 该分类下有 {{ deleteTarget.item_count }} 种商品，删除后商品将失去分类关联。
          </span>
        </p>
        <div class="modal-btns">
          <button class="btn-cancel" @click="deleteTarget = null">{{ $t('cancel') }}</button>
          <button class="btn-save btn-danger" @click="doDelete">
            {{ $t('delete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const categories = ref([])
const showModal = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const saving = ref(false)
const deleting = ref(false)

const form = ref({ name: '', icon: '📦' })

const emojiList = [
  '🍎','🥤','🧴','🧹','💊','🍫','🧂','📦',
  '🥩','🥚','🍞','🧃','🍵','🫙','🧊','🛒',
  '👶','🐾','📱','💡','🔧','🌿','🎁','🧺',
]

async function loadCategories() {
  try {
    const res = await api.getCategories()
    categories.value = res.data
  } catch (e) {
    console.error(e)
  }
}

function openAdd() {
  editTarget.value = null
  form.value = { name: '', icon: '📦' }
  showModal.value = true
}

function openEdit(cat) {
  editTarget.value = cat
  form.value = { name: cat.name, icon: cat.icon || '📦' }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editTarget.value = null
}

async function save() {
  if (!form.value.name.trim() || saving.value) return
  saving.value = true
  try {
    if (editTarget.value) {
      await api.updateCategory(editTarget.value.id, form.value)
    } else {
      await api.createCategory(form.value)
    }
    closeModal()
    await loadCategories()
  } catch (e) {
    alert(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(cat) {
  deleteTarget.value = cat
}

async function doDelete() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await api.deleteCategory(deleteTarget.value.id)
    deleteTarget.value = null
    await loadCategories()
  } catch (e) {
    alert(e.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(loadCategories)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; font-weight: 700; }

.btn-add {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.cat-list { display: flex; flex-direction: column; gap: 10px; }

.cat-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.cat-main { display: flex; align-items: center; gap: 12px; }
.cat-emoji { font-size: 28px; }
.cat-name { font-weight: 600; font-size: 15px; }
.cat-count { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.cat-actions { display: flex; gap: 8px; }
.btn-icon {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: background 0.15s;
}
.btn-icon:hover { background: var(--border); }

.empty {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
  font-size: 14px;
}

/* 弹窗 */
.modal-mask {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.45);
  display: flex; align-items: flex-end; justify-content: center;
  z-index: 200;
}
.modal {
  background: var(--bg);
  border-radius: 16px 16px 0 0;
  padding: 24px 20px 32px;
  width: 100%;
  max-width: 480px;
}
.modal-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 16px;
  text-align: center;
}

.emoji-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.emoji-opt {
  font-size: 22px;
  padding: 6px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  border: 2px solid transparent;
}
.emoji-opt:hover { background: var(--border); }
.emoji-opt.active {
  border-color: var(--primary);
  background: rgba(79, 70, 229, 0.1);
}

.input {
  width: 100%;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  background: var(--card);
  color: var(--text);
  box-sizing: border-box;
  margin-bottom: 16px;
}
.input:focus { outline: none; border-color: var(--primary); }

.modal-btns {
  display: flex;
  gap: 10px;
}
.btn-cancel, .btn-save {
  flex: 1;
  padding: 13px;
  border-radius: 10px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.btn-cancel {
  background: var(--border);
  color: var(--text);
}
.btn-save {
  background: var(--primary);
  color: #fff;
}
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { background: #EF4444; }

.del-tip {
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 16px;
  line-height: 1.6;
}
.warn-text { color: #EF4444; }
</style>
