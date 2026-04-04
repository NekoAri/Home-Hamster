# 🐹 Home Hamster

> 家庭仓库管理系统 — 一只为家庭设计的轻量级库存管理小仓鼠。

支持扫码录入、有效期追踪、临期/过期预警、库存统计分析、智能补货建议，可通过 Homebridge 接入 HomeKit 实现智能通知。

![技术栈](https://img.shields.io/badge/Vue_3-前端-42b883?logo=vue.js)
![技术栈](https://img.shields.io/badge/Node.js-后端-339933?logo=node.js)
![技术栈](https://img.shields.io/badge/PWA-可安装-5C2D91?logo=pwa)

## ✨ 功能特性

- 📷 **扫码入库** — 扫描条形码快速添加商品
- 🖼️ **图片管理** — 拍照上传商品照片
- 📅 **有效期追踪** — 记录生产日期和有效期，临期自动预警
- ⚠️ **临期/过期独立页面** — 专属列表查看即将过期和已过期的商品
- 📊 **统计分析** — 按分类统计、消耗趋势图表、补货建议
- 🎨 **主题自定义** — 12 种预设颜色 + 自定义取色器
- 🌐 **中英双语** — 内置轻量 i18n，支持中文 / English 切换
- 🏡 **HomeKit 集成** — 临期 / 低库存自动推送通知
- 📱 **PWA 离线可用** — 添加到主屏幕，像原生 App 一样使用

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Node.js + Express | 轻量 HTTP 服务 |
| 数据库 | LowDB (JSON) / SQLite (可选) | 默认 JSON 文件存储，可切换 SQLite |
| 前端 | Vue 3 + Vite | 响应式 SPA |
| 样式 | CSS Variables 主题系统 | 可动态切换主题色 |
| 扫码 | 浏览器摄像头 API + QuaggaJS | 条形码识别 |
| 国际化 | 自研轻量 i18n (Vue reactive) | 无第三方依赖 |
| HomeKit | 自定义 Homebridge 插件 | 临期/低库存传感器 |

## 📁 项目结构

```
home-inventory/
├── server/                # 后端服务
│   ├── index.js           # 主入口（HTTP 3000 / HTTPS 3443）
│   ├── db/
│   │   ├── schema.js      # JSON 数据库 (LowDB + SQLite 兼容接口)
│   │   └── sqlite-adapter.js
│   ├── routes/            # API 路由
│   │   ├── items.js       # 商品 CRUD
│   │   ├── inventory.js   # 库存管理
│   │   ├── categories.js  # 分类管理
│   │   ├── stats.js       # 统计分析
│   │   └── settings.js    # 应用设置
│   ├── data/              # 数据存储（db.json）
│   └── uploads/           # 商品图片
├── client/                # 前端应用 (Vue 3 + Vite)
│   ├── src/
│   │   ├── views/         # 页面组件
│   │   ├── api/           # API 封装
│   │   ├── i18n/          # 国际化
│   │   └── App.vue        # 根组件 + 全局样式
│   ├── public/            # 静态资源 (logo, PWA icons)
│   └── vite.config.js     # Vite + PWA 配置
└── homebridge-plugin/     # Homebridge 插件
```

## 🚀 快速开始

### 环境要求

- Node.js >= 18
- npm

### 1. 安装后端依赖

```bash
cd server
npm install
```

### 2. 安装前端依赖并构建

```bash
cd ../client
npm install
npm run build
```

### 3. 启动服务

```bash
cd ../server
npm start          # 生产模式
# 或
npm run dev        # 开发模式（nodemon 热重载）
```

服务启动后：
- HTTP: `http://localhost:3000`
- HTTPS: `https://localhost:3443`（自动生成自签名证书）

### 4. 访问应用

- 本机：`http://localhost:3000`
- 局域网：`http://<设备IP>:3000`

### 5. 安装 Homebridge 插件（可选）

```bash
cd homebridge-plugin
npm link
# 然后在 Homebridge 配置中添加插件
```

## 📱 PWA 安装

在手机浏览器中打开应用：

- **iOS Safari**：点击"分享" → "添加到主屏幕"
- **Android Chrome**：点击地址栏右侧 → "添加到主屏幕"

添加后即可像原生 App 一样从桌面直接打开。

## 🎨 主题与个性化

应用内置主题系统，可在设置页自由切换：

- 12 种预设主题色（仓鼠棕、翡翠绿、玫瑰红等）
- 自定义取色器选择任意颜色
- 主题色保存到 localStorage，刷新后自动恢复
- 全局 CSS 变量驱动，一处修改全局生效

## 🌐 语言切换

支持中文（简体）和英文：

- 首次访问自动检测系统语言
- 在设置页可手动切换语言
- 语言偏好保存到 localStorage

## 🏡 HomeKit 自动化

安装 Homebridge 插件后，在 Home App 中创建自动化：

1. **临期提醒**
   - 触发条件："临期传感器"状态变为"检测到"
   - 动作：发送通知"有物品即将过期！"

2. **库存不足提醒**
   - 触发条件："库存传感器"状态变为"检测到"
   - 动作：发送通知"有商品库存不足！"

## 🔧 开机自启

### macOS (LaunchAgent)

创建 `~/Library/LaunchAgents/com.homeinventory.server.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.homeinventory.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/node</string>
        <string>/path/to/home-inventory/server/index.js</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/path/to/home-inventory/server</string>
</dict>
</plist>
```

加载配置：

```bash
launchctl load ~/Library/LaunchAgents/com.homeinventory.server.plist
```

### Windows (Task Scheduler / PowerShell)

使用 PowerShell 后台任务启动：

```powershell
Start-Job { & node "C:\path\to\home-inventory\server\index.js" }
```

如需开机自启，可在"任务计划程序"中创建基本任务，触发器设为"计算机启动时"。

## 📡 API 文档

### 统计分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats/overview` | 仪表盘概览数据 |
| GET | `/api/stats/expiring?days=30` | 临期/过期物品列表 |
| GET | `/api/stats/low-stock` | 库存不足列表 |
| GET | `/api/stats/suggestions` | 智能补货建议 |
| GET | `/api/stats/by-category` | 按分类统计 |
| GET | `/api/stats/consumption?days=30` | 消耗趋势 |
| GET | `/api/stats/homekit` | Homebridge 专用接口 |

### 商品管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/items` | 商品列表（支持搜索、分类过滤、分页） |
| GET | `/api/items/:id` | 商品详情（含库存批次） |
| GET | `/api/items/barcode/:barcode` | 条码查询 |
| POST | `/api/items` | 创建商品（支持图片上传） |
| PUT | `/api/items/:id` | 更新商品 |
| DELETE | `/api/items/:id` | 删除商品（级联删除库存和消耗记录） |

### 库存管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/inventory` | 添加库存批次 |
| PUT | `/api/inventory/:id` | 更新库存 |
| DELETE | `/api/inventory/:id` | 删除库存批次 |
| POST | `/api/inventory/:id/consume` | 消耗库存 |

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 分类列表 |
| GET | `/api/health` | 健康检查 |

## 📝 License

MIT
