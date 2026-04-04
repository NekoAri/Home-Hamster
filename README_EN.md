# 🐹 Home Hamster

> A lightweight home inventory management tool — your little hamster helper for keeping track of household stock.

Supports barcode scanning, expiry date tracking, approaching/expired item alerts, inventory analytics, smart restocking suggestions, and HomeKit integration via Homebridge for smart notifications.

![Tech](https://img.shields.io/badge/Vue_3-Frontend-42b883?logo=vue.js)
![Tech](https://img.shields.io/badge/Node.js-Backend-339933?logo=node.js)
![Tech](https://img.shields.io/badge/PWA-Installable-5C2D91?logo=pwa)

## ✨ Features

- 📷 **Barcode Scanning** — Quickly add items by scanning barcodes
- 🖼️ **Photo Management** — Take photos or upload product images
- 📅 **Expiry Tracking** — Record production and expiry dates with automatic near-expiry alerts
- ⚠️ **Dedicated Expiry Pages** — Dedicated lists for items approaching expiry and already expired
- 📊 **Analytics** — Category-based statistics, consumption trend charts, restocking suggestions
- 🎨 **Custom Themes** — 12 preset colors + custom color picker
- 🌐 **Bilingual** — Built-in lightweight i18n supporting Chinese (简体) / English
- 🏡 **HomeKit Integration** — Automatic push notifications for near-expiry and low stock items
- 📱 **PWA Offline Support** — Add to home screen and use like a native app

## 🛠️ Tech Stack

| Layer | Technology | Description |
|-------|-----------|-------------|
| Backend | Node.js + Express | Lightweight HTTP server |
| Database | LowDB (JSON) / SQLite (optional) | JSON file storage by default, switchable to SQLite |
| Frontend | Vue 3 + Vite | Reactive SPA |
| Styling | CSS Variables theme system | Dynamic theme color switching |
| Scanning | Browser Camera API + QuaggaJS | Barcode recognition |
| i18n | Custom lightweight i18n (Vue reactive) | No third-party dependencies |
| HomeKit | Custom Homebridge plugin | Near-expiry / low stock sensors |

## 📁 Project Structure

```
home-inventory/
├── server/                # Backend service
│   ├── index.js           # Main entry (HTTP 3000 / HTTPS 3443)
│   ├── db/
│   │   ├── schema.js      # JSON database (LowDB + SQLite-compatible interface)
│   │   └── sqlite-adapter.js
│   ├── routes/            # API routes
│   │   ├── items.js       # Item CRUD
│   │   ├── inventory.js   # Inventory management
│   │   ├── categories.js  # Category management
│   │   ├── stats.js       # Analytics & statistics
│   │   └── settings.js    # App settings
│   ├── data/              # Data storage (db.json)
│   └── uploads/           # Product images
├── client/                # Frontend app (Vue 3 + Vite)
│   ├── src/
│   │   ├── views/         # Page components
│   │   ├── api/           # API layer
│   │   ├── i18n/          # Internationalization
│   │   └── App.vue        # Root component + global styles
│   ├── public/            # Static assets (logo, PWA icons)
│   └── vite.config.js     # Vite + PWA config
└── homebridge-plugin/     # Homebridge plugin
```

## 🚀 Quick Start

### Prerequisites

- Node.js >= 18
- npm

### 1. Install Backend Dependencies

```bash
cd server
npm install
```

### 2. Install Frontend Dependencies & Build

```bash
cd ../client
npm install
npm run build
```

### 3. Start the Server

```bash
cd ../server
npm start          # Production mode
# or
npm run dev        # Development mode (nodemon hot reload)
```

After starting:
- HTTP: `http://localhost:3000`
- HTTPS: `https://localhost:3443` (auto-generated self-signed certificate)

### 4. Access the App

- Local: `http://localhost:3000`
- LAN: `http://<device-ip>:3000`

### 5. Install Homebridge Plugin (Optional)

```bash
cd homebridge-plugin
npm link
# Then add the plugin in your Homebridge configuration
```

## 📱 PWA Installation

Open the app in your mobile browser:

- **iOS Safari**: Tap "Share" → "Add to Home Screen"
- **Android Chrome**: Tap the address bar menu → "Add to Home Screen"

Once added, you can launch it directly from your home screen like a native app.

## 🎨 Themes & Personalization

The app features a built-in theme system, freely switchable in Settings:

- 12 preset theme colors (Hamster Brown, Emerald Green, Rose Red, etc.)
- Custom color picker for any color
- Theme color saved to localStorage, automatically restored on refresh
- Driven by global CSS variables — change once, apply everywhere

## 🌐 Language Switching

Supports Chinese (Simplified) and English:

- Automatically detects system language on first visit
- Manually switch language in Settings
- Language preference saved to localStorage

## 🏡 HomeKit Automation

After installing the Homebridge plugin, create automations in the Home app:

1. **Near-Expiry Reminder**
   - Trigger: "Near-Expiry Sensor" state changes to "Detected"
   - Action: Send notification "Items are approaching expiry!"

2. **Low Stock Reminder**
   - Trigger: "Low Stock Sensor" state changes to "Detected"
   - Action: Send notification "Some items are running low on stock!"

## 🔧 Auto-Start on Boot

### macOS (LaunchAgent)

Create `~/Library/LaunchAgents/com.homeinventory.server.plist`:

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

Load the configuration:

```bash
launchctl load ~/Library/LaunchAgents/com.homeinventory.server.plist
```

### Windows (Task Scheduler / PowerShell)

Start as a PowerShell background job:

```powershell
Start-Job { & node "C:\path\to\home-inventory\server\index.js" }
```

For auto-start on boot, create a Basic Task in Task Scheduler with the trigger set to "At computer startup".

## 📡 API Reference

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats/overview` | Dashboard overview data |
| GET | `/api/stats/expiring?days=30` | Near-expiry / expired items list |
| GET | `/api/stats/low-stock` | Low stock items list |
| GET | `/api/stats/suggestions` | Smart restocking suggestions |
| GET | `/api/stats/by-category` | Category-based statistics |
| GET | `/api/stats/consumption?days=30` | Consumption trends |
| GET | `/api/stats/homekit` | Homebridge-specific endpoint |

### Item Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/items` | Item list (search, category filter, pagination) |
| GET | `/api/items/:id` | Item details (with inventory batches) |
| GET | `/api/items/barcode/:barcode` | Barcode lookup |
| POST | `/api/items` | Create item (supports image upload) |
| PUT | `/api/items/:id` | Update item |
| DELETE | `/api/items/:id` | Delete item (cascades to inventory & consumption logs) |

### Inventory Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/inventory` | Add inventory batch |
| PUT | `/api/inventory/:id` | Update inventory |
| DELETE | `/api/inventory/:id` | Delete inventory batch |
| POST | `/api/inventory/:id/consume` | Consume inventory |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/categories` | Category list |
| GET | `/api/health` | Health check |

## 📝 License

MIT
