// 轻量级国际化 - 基于 Vue 响应式系统
// 无需安装额外依赖，直接使用 reactive + provide/inject

import { reactive, watch } from 'vue'

// 语言包
const messages = {
  'zh-CN': {
    // 通用
    appName: 'Home Hamster',
    save: '保存',
    cancel: '取消',
    delete: '删除',
    edit: '编辑',
    confirm: '确认',
    add: '添加',
    search: '搜索',
    all: '全部',
    noData: '暂无数据',
    loading: '加载中...',
    success: '操作成功',
    error: '操作失败',
    saveSuccess: '保存成功',
    deleteConfirm: '确定要删除吗？',
    yes: '是',
    no: '否',

    // 导航
    navHome: '首页',
    navInventory: '库存',
    navScan: '扫码',
    navStats: '统计',
    navCategories: '分类',

    // 首页
    greeting: 'Home Hamster 🐹',
    expiringSoon: '30天内临期',
    expired: '已过期',
    expiringAlert: '临期提醒',
    viewAll: '查看全部',
    viewMore: '查看更多',
    expiringPageTitle: '临期物品',
    expiredPageTitle: '已过期物品',
    expiringTab: '临期',
    expiredTab: '已过期',
    noExpiringItems: '暂无临期物品',
    noExpiredItems: '暂无已过期物品',
    scanToStock: '扫码入库',
    scanToConsume: '扫码出库',
    manualAdd: '手动添加',
    viewInventory: '查看库存',
    statsAnalysis: '统计分析',
    daysText: '{days}天',
    expiryInfo: '{date} 到期 · 剩余 {qty}{unit}',

    // 库存
    inventoryList: '库存列表',
    searchPlaceholder: '🔍 搜索商品名称或条码',
    noItems: '暂无商品，去添加吧',
    uncategorized: '未分类',
    nearestExpiry: '最近到期：{date}',

    // 扫码
    scanTitle: '扫码',
    startCamera: '开启摄像头',
    stopCamera: '关闭摄像头',
    scanHint: '将条形码对准摄像头',
    manualInput: '手动输入条码',
    manualInputPlaceholder: '输入条形码',
    searchBarcode: '搜索',
    notFound: '未找到商品',
    foundItem: '找到已有商品',
    createNew: '创建新商品',
    addStock: '📦 添加库存',
    consumeStock: '🍽️ 消耗库存',
    currentStock: '当前总库存',
    addStockTitle: '添加库存',
    consumeTitle: '消耗库存',
    consumeQuantity: '消耗数量',
    quantity: '数量',
    productionDate: '生产日期',
    expiryDate: '有效期至',
    location: '存放位置',
    locationPlaceholder: '如：冰箱、储物柜',
    notes: '备注',
    notesPlaceholder: '可选',
    confirmAdd: '确认添加',
    confirmConsume: '确认消耗',
    noStock: '暂无库存可消耗',
    consumeSuccess: '✅ 消耗成功！',
    consumeFailed: '消耗失败',

    // 添加物品
    addItem: '添加商品',
    itemName: '商品名称',
    itemNamePlaceholder: '输入商品名称',
    barcode: '条形码',
    barcodePlaceholder: '扫码或手动输入',
    category: '分类',
    selectCategory: '选择分类',
    unit: '单位',
    unitPlaceholder: '如：个、瓶、袋',
    defaultUnit: '个',
    minStock: '最低库存',
    minStockPlaceholder: '库存低于此数量时提醒',
    itemNotes: '备注',
    itemNotesPlaceholder: '可选备注',
    uploadImage: '📷 上传图片',
    removeImage: '点击移除图片',
    initialStock: '初始库存',
    saving: '保存中...',
    saveItem: '保存商品',
    nameRequired: '请输入商品名称',

    // 编辑物品
    editItem: '编辑商品',
    updateSuccess: '更新成功',

    // 商品详情
    itemDetail: '商品详情',
    stockTotal: '库存总量',
    stockBatch: '库存批次',
    addStockBtn: '+ 添加库存',
    consumeBtn: '消耗',
    editBtn: '编辑',

    // 分类
    categoryManage: '分类管理',
    categoryName: '分类名称',
    categoryNamePlaceholder: '输入分类名称',
    categoryIcon: '图标',
    editCategory: '编辑分类',
    addCategory: '添加分类',
    noCategories: '暂无分类，添加一个吧',

    // 统计
    statsTitle: '统计分析',
    byCategory: '按分类统计',
    expiringItems: '临期物品（30天内）',
    lowStockList: '库存不足',
    consumptionTrend: '近30天消耗趋势',
    restockSuggestion: '智能补货建议',
    noExpiring: '🎉 暂无临期物品',
    stockSufficient: '✅ 库存充足',
    noConsumption: '暂无消耗记录',
    noSuggestion: '🎉 暂无补货建议',
    itemsCount: '{count} 种商品 · {stock} 件',
    urgent: '急需',
    restock: '建议补货',
    consumptionLabel: '消耗数量',
    stockInfo: '当前 {cur}{unit} · 最低 {min}{unit}',
    dailyAvg: '日均消耗 {avg}{unit}',
    daysRemaining: '预计{days}天用完',
    insufficient: '不足',

    // 设置
    settings: '设置',
    language: '语言',
    languageDesc: '选择系统显示语言',

    // 数据库设置
    dbConfig: '数据库配置',
    dbConfigDesc: '选择数据存储方式',
    dbTypeJson: 'JSON 文件（默认）',
    dbTypeJsonDesc: '数据存储在本地 JSON 文件中，无需额外配置',
    dbTypeSqlite: 'SQLite 数据库',
    dbTypeSqliteDesc: '数据存储在 SQLite 文件中，适合更大量数据和高级查询',
    dbPath: '数据库路径',
    dbPathPlaceholder: '如：/path/to/inventory.db',
    dbPassword: '数据库密码（可选）',
    dbPasswordPlaceholder: '留空表示不加密',
    dbTestConnection: '测试连接',
    dbTestSuccess: '连接成功！',
    dbTestFailed: '连接失败',
    dbSaveSuccess: '保存成功，重启服务后生效',
    dbSaveFailed: '保存失败',
    dbSave: '保存配置',
    dbCurrentType: '当前数据库：{type}',

    // 主题设置
    themeColor: '主题颜色',
    themeColorDesc: '自定义应用的主色调',
    themePreset: '预设颜色',
    themeCustom: '自定义颜色',
    themeApplied: '主题已应用',

    // 语言选择页
    selectLanguage: '选择语言',
    selectLanguageDesc: '请选择您偏好的语言',
    chinese: '中文',
    english: 'English',

    // 更新提示
    updateAvailable: '发现新版本，点击更新',
    updateNow: '立即更新',
  },

  'en': {
    // 通用
    appName: 'Home Hamster',
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    edit: 'Edit',
    confirm: 'Confirm',
    add: 'Add',
    search: 'Search',
    all: 'All',
    noData: 'No data',
    loading: 'Loading...',
    success: 'Success',
    error: 'Error',
    saveSuccess: 'Saved successfully',
    deleteConfirm: 'Are you sure you want to delete?',
    yes: 'Yes',
    no: 'No',

    // 导航
    navHome: 'Home',
    navInventory: 'Stock',
    navScan: 'Scan',
    navStats: 'Stats',
    navCategories: 'Tags',

    // 首页
    greeting: 'Home Hamster 🐹',
    expiringSoon: 'Expiring in 30 days',
    expired: 'Expired',
    expiringAlert: 'Expiry Alerts',
    viewAll: 'View All',
    viewMore: 'View More',
    expiringPageTitle: 'Expiring Items',
    expiredPageTitle: 'Expired Items',
    expiringTab: 'Expiring',
    expiredTab: 'Expired',
    noExpiringItems: 'No expiring items',
    noExpiredItems: 'No expired items',
    scanToStock: 'Scan to Add',
    scanToConsume: 'Scan to Use',
    manualAdd: 'Add Manually',
    viewInventory: 'View Stock',
    statsAnalysis: 'Statistics',
    daysText: '{days} days',
    expiryInfo: 'Expires {date} · {qty}{unit} left',

    // 库存
    inventoryList: 'Inventory',
    searchPlaceholder: '🔍 Search name or barcode',
    noItems: 'No items yet. Add one!',
    uncategorized: 'Uncategorized',
    nearestExpiry: 'Nearest expiry: {date}',

    // 扫码
    scanTitle: 'Scan',
    startCamera: 'Start Camera',
    stopCamera: 'Stop Camera',
    scanHint: 'Point the camera at the barcode',
    manualInput: 'Manual Input',
    manualInputPlaceholder: 'Enter barcode',
    searchBarcode: 'Search',
    notFound: 'Item not found',
    foundItem: 'Item Found',
    createNew: 'Create New Item',
    addStock: '📦 Add Stock',
    consumeStock: '🍽️ Consume',
    currentStock: 'Current stock',
    addStockTitle: 'Add Stock',
    consumeTitle: 'Consume Stock',
    consumeQuantity: 'Quantity',
    quantity: 'Quantity',
    productionDate: 'Production Date',
    expiryDate: 'Expiry Date',
    location: 'Location',
    locationPlaceholder: 'e.g. Fridge, Pantry',
    notes: 'Notes',
    notesPlaceholder: 'Optional',
    confirmAdd: 'Confirm',
    confirmConsume: 'Confirm',
    noStock: 'No stock available',
    consumeSuccess: '✅ Consumed!',
    consumeFailed: 'Failed',

    // 添加物品
    addItem: 'Add Item',
    itemName: 'Item Name',
    itemNamePlaceholder: 'Enter item name',
    barcode: 'Barcode',
    barcodePlaceholder: 'Scan or enter barcode',
    category: 'Category',
    selectCategory: 'Select category',
    unit: 'Unit',
    unitPlaceholder: 'e.g. pcs, bottle, bag',
    defaultUnit: 'pcs',
    minStock: 'Min Stock',
    minStockPlaceholder: 'Alert when stock below this',
    itemNotes: 'Notes',
    itemNotesPlaceholder: 'Optional notes',
    uploadImage: '📷 Upload Image',
    removeImage: 'Click to remove',
    initialStock: 'Initial Stock',
    saving: 'Saving...',
    saveItem: 'Save Item',
    nameRequired: 'Item name is required',

    // 编辑物品
    editItem: 'Edit Item',
    updateSuccess: 'Updated successfully',

    // 商品详情
    itemDetail: 'Item Detail',
    stockTotal: 'Total Stock',
    stockBatch: 'Stock Batches',
    addStockBtn: '+ Add Stock',
    consumeBtn: 'Use',
    editBtn: 'Edit',

    // 分类
    categoryManage: 'Categories',
    categoryName: 'Category Name',
    categoryNamePlaceholder: 'Enter category name',
    categoryIcon: 'Icon',
    editCategory: 'Edit Category',
    addCategory: 'Add Category',
    noCategories: 'No categories yet. Add one!',

    // 统计
    statsTitle: 'Statistics',
    byCategory: 'By Category',
    expiringItems: 'Expiring (30 days)',
    lowStockList: 'Low Stock',
    consumptionTrend: '30-Day Consumption Trend',
    restockSuggestion: 'Restock Suggestions',
    noExpiring: '🎉 No expiring items',
    stockSufficient: '✅ Stock is sufficient',
    noConsumption: 'No consumption data',
    noSuggestion: '🎉 No suggestions',
    itemsCount: '{count} items · {stock} units',
    urgent: 'Urgent',
    restock: 'Restock',
    consumptionLabel: 'Consumed',
    stockInfo: '{cur}{unit} · min {min}{unit}',
    dailyAvg: 'Avg {avg}{unit}/day',
    daysRemaining: '~{days} days left',
    insufficient: 'Low',

    // 设置
    settings: 'Settings',
    language: 'Language',
    languageDesc: 'Choose display language',

    // Database settings
    dbConfig: 'Database',
    dbConfigDesc: 'Choose data storage method',
    dbTypeJson: 'JSON File (Default)',
    dbTypeJsonDesc: 'Data stored in local JSON file, no setup needed',
    dbTypeSqlite: 'SQLite Database',
    dbTypeSqliteDesc: 'Data stored in SQLite file, for larger datasets',
    dbPath: 'Database Path',
    dbPathPlaceholder: 'e.g. /path/to/inventory.db',
    dbPassword: 'Password (Optional)',
    dbPasswordPlaceholder: 'Leave empty for no encryption',
    dbTestConnection: 'Test Connection',
    dbTestSuccess: 'Connection successful!',
    dbTestFailed: 'Connection failed',
    dbSaveSuccess: 'Saved! Restart required.',
    dbSaveFailed: 'Save failed',
    dbSave: 'Save Config',
    dbCurrentType: 'Current: {type}',

    // Theme settings
    themeColor: 'Theme Color',
    themeColorDesc: 'Customize the primary color of the app',
    themePreset: 'Preset Colors',
    themeCustom: 'Custom Color',
    themeApplied: 'Theme applied',

    // 语言选择页
    selectLanguage: 'Select Language',
    selectLanguageDesc: 'Please choose your preferred language',
    chinese: '中文',
    english: 'English',

    // 更新提示
    updateAvailable: 'New version available',
    updateNow: 'Update',
  }
}

// 获取保存的语言，默认中文
function getSavedLocale() {
  return localStorage.getItem('app-locale') || 'zh-CN'
}

// 响应式当前语言
const locale = reactive({ value: getSavedLocale() })

// 当前语言的消息对象（响应式）
const currentMessages = reactive({})

// 更新消息
function updateMessages() {
  const msg = messages[locale.value] || messages['zh-CN']
  Object.keys(msg).forEach(key => {
    currentMessages[key] = msg[key]
  })
}
updateMessages()

// 切换语言
function setLocale(newLocale) {
  if (!messages[newLocale]) return
  locale.value = newLocale
  localStorage.setItem('app-locale', newLocale)
  updateMessages()
}

// 翻译函数，支持简单的 {key} 模板替换
// 例如：t('expiryInfo', { date: '2024-01', qty: 5, unit: '个' })
//       t('daysText', { days: 3 })
function t(key, params = {}) {
  let text = currentMessages[key] || messages['zh-CN'][key] || key
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v)
    })
  }
  return text
}

// 可用语言列表
const availableLocales = [
  { code: 'zh-CN', label: '中文' },
  { code: 'en', label: 'English' },
]

// 判断是否首次访问（未设置过语言）
function isFirstVisit() {
  return !localStorage.getItem('app-locale')
}

export {
  locale,
  t,
  setLocale,
  availableLocales,
  isFirstVisit,
  currentMessages,
}

export default {
  install(app) {
    // 全局属性，让所有组件可以通过 this.$t() 使用
    app.config.globalProperties.$t = t
    app.config.globalProperties.$locale = locale
    app.config.globalProperties.$setLocale = setLocale
    app.provide('i18n', { t, locale, setLocale })
  }
}
