import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import i18n from './i18n/index.js'

// 路由
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',         component: () => import('./views/Home.vue'),      meta: { title: '首页' } },
    { path: '/inventory',component: () => import('./views/Inventory.vue'), meta: { title: '库存' } },
    { path: '/scan',     component: () => import('./views/Scan.vue'),      meta: { title: '扫码' } },
    { path: '/stats',    component: () => import('./views/Stats.vue'),     meta: { title: '统计' } },
    { path: '/item/:id', component: () => import('./views/ItemDetail.vue'),meta: { title: '详情' } },
    { path: '/item/:id/edit', component: () => import('./views/EditItem.vue'), meta: { title: '编辑' } },
    { path: '/add-item', component: () => import('./views/AddItem.vue'),   meta: { title: '添加' } },
    { path: '/categories', component: () => import('./views/Categories.vue'), meta: { title: '分类管理' } },
    { path: '/settings', component: () => import('./views/Settings.vue'), meta: { title: '设置' } },
    { path: '/expiring', component: () => import('./views/ExpiringItems.vue'), meta: { title: '临期物品', hideNav: true } },
    { path: '/setup-language', component: () => import('./views/SetupLanguage.vue'), meta: { title: '语言选择', hideNav: true } },
  ]
})

router.afterEach((to) => {
  document.title = `${to.meta.title || ''} — 家庭仓库`
})

createApp(App).use(router).use(i18n).mount('#app')
