// API 基础封装
const BASE = '/api'

async function request(path, options = {}) {
  const headers = { ...options.headers }
  // 只在有 body 时设置 Content-Type，避免 DELETE 等无 body 请求发送不必要的 header
  if (options.body) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
  }
  const res = await fetch(BASE + path, {
    ...options,
    headers,
  })
  const data = await res.json()
  if (!data.success) throw new Error(data.message || '请求失败')
  return data
}

// 分类
export const api = {
  // 概览
  getOverview: () => request('/stats/overview'),
  getExpiring: (days = 30) => request(`/stats/expiring?days=${days}`),
  getLowStock: () => request('/stats/low-stock'),
  getSuggestions: () => request('/stats/suggestions'),
  getByCategory: () => request('/stats/by-category'),
  getConsumption: (days = 30, item_id) =>
    request(`/stats/consumption?days=${days}${item_id ? '&item_id=' + item_id : ''}`),

  // 分类
  getCategories: () => request('/categories'),
  createCategory: (data) => request('/categories', { method: 'POST', body: JSON.stringify(data) }),
  updateCategory: (id, data) => request(`/categories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCategory: (id) => request(`/categories/${id}`, { method: 'DELETE' }),

  // 商品
  getItems: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/items${q ? '?' + q : ''}`)
  },
  getItem: (id) => request(`/items/${id}`),
  getItemByBarcode: (barcode) => request(`/items/barcode/${barcode}`),
  createItem: (formData) => fetch(BASE + '/items', { method: 'POST', body: formData }).then(r => r.json()),
  updateItem: (id, formData) => fetch(BASE + `/items/${id}`, { method: 'PUT', body: formData }).then(r => r.json()),
  deleteItem: (id) => request(`/items/${id}`, { method: 'DELETE' }),

  // 库存
  addInventory: (data) => request('/inventory', { method: 'POST', body: JSON.stringify(data) }),
  updateInventory: (id, data) => request(`/inventory/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteInventory: (id) => request(`/inventory/${id}`, { method: 'DELETE' }),
  consumeInventory: (id, quantity, notes) =>
    request(`/inventory/${id}/consume`, { method: 'POST', body: JSON.stringify({ quantity, notes }) }),

  // 设置
  getDbConfig: () => request('/settings/database'),
  saveDbConfig: (data) => request('/settings/database', { method: 'PUT', body: JSON.stringify(data) }),
  testDbConnection: (data) => request('/settings/database/test', { method: 'POST', body: JSON.stringify(data) }),
}
