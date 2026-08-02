<template>
  <div class="page">
    <div class="page-header">
      <span class="page-title">{{ $t('inventoryList') }}</span>
      <router-link to="/add-item" class="btn btn-primary" style="padding:8px 14px;font-size:14px">+ {{ $t('add') }}</router-link>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <input v-model="search" class="form-input" :placeholder="$t('searchPlaceholder')" @input="onSearch" />
    </div>

    <!-- 分类过滤 -->
    <div class="category-tabs">
      <button
        v-for="cat in [{ id: '', name: $t('all'), icon: '🏷️' }, ...categories]"
        :key="cat.id"
        class="cat-tab"
        :class="{ active: selectedCategory === cat.id }"
        @click="selectCategory(cat.id)"
      >{{ cat.icon }} {{ cat.name }}</button>
    </div>

    <!-- 库存列表 -->
    <div v-if="items.length > 0">
      <div v-for="item in items" :key="item.id" class="item-card" @click="$router.push('/item/' + item.id)">
        <div class="item-img-wrap">
          <img v-if="item.image_path" :src="item.image_path" class="item-img" />
          <div v-else class="item-img-placeholder">{{ item.category_icon || '📦' }}</div>
        </div>
        <div class="item-info">
          <div class="item-name">{{ item.name }}</div>
          <div class="item-meta">{{ item.category_icon }} {{ item.category_name || $t('uncategorized') }}</div>
          <div class="item-stock">
            <span :class="['badge', item.total_stock <= item.min_stock ? 'badge-danger' : 'badge-success']">
              {{ item.total_stock }} {{ item.unit }}
            </span>
            <span v-if="item.nearest_expiry" class="expiry-text">
              {{ $t('nearestExpiry', { date: item.nearest_expiry }) }}
            </span>
          </div>
        </div>
        <span class="item-arrow">›</span>
      </div>
    </div>

    <div v-else class="empty">
      <div class="empty-icon">📭</div>
      <div class="empty-text">{{ $t('noItems') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'

const items = ref([])
const categories = ref([])
const search = ref('')
const selectedCategory = ref('')
let searchTimer = null

const loadItems = async () => {
  const params = {}
  if (search.value) params.search = search.value
  if (selectedCategory.value) params.category_id = selectedCategory.value
  const res = await api.getItems(params)
  items.value = res.data
}

const onSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadItems, 300)
}

const selectCategory = (id) => {
  selectedCategory.value = id
  loadItems()
}

onMounted(async () => {
  const [itemsRes, catsRes] = await Promise.all([api.getItems(), api.getCategories()])
  items.value = itemsRes.data
  categories.value = catsRes.data
})
</script>

<style scoped>
.search-bar { margin-bottom: 12px; }
.category-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 12px;
  scrollbar-width: none;
}
.category-tabs::-webkit-scrollbar { display: none; }
.cat-tab {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 99px;
  border: 1.5px solid var(--border);
  background: var(--card);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all .2s;
}
.cat-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.item-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  cursor: pointer;
  transition: transform .1s;
}
.item-card:active { transform: scale(.99); }

.item-img-wrap { flex-shrink: 0; }
.item-img {
  width: 56px; height: 56px;
  border-radius: 10px;
  object-fit: cover;
}
.item-img-placeholder {
  width: 56px; height: 56px;
  border-radius: 10px;
  background: var(--primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.item-info { flex: 1; min-width: 0; }
.item-name { font-weight: 700; font-size: 15px; margin-bottom: 3px; }
.item-meta { font-size: 12px; color: var(--text-muted); margin-bottom: 5px; }
.item-stock { display: flex; align-items: center; gap: 8px; }
.expiry-text { font-size: 12px; color: var(--warning); }

.item-arrow { color: var(--text-muted); font-size: 20px; flex-shrink: 0; }
</style>
