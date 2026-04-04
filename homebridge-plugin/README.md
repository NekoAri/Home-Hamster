# Homebridge Home Inventory Plugin

家庭仓库管理系统的 Homebridge 插件，将库存状态暴露为 HomeKit 传感器。

## 安装

```bash
npm install -g homebridge-home-inventory
```

## 配置

在 Homebridge `config.json` 中添加：

```json
{
  "platforms": [
    {
      "platform": "HomeInventory",
      "name": "家庭仓库",
      "serverUrl": "http://localhost:3000",
      "checkInterval": 60,
      "expiringDays": 7
    }
  ]
}
```

## 传感器说明

| 传感器 | 类型 | 触发条件 |
|--------|------|---------|
| 临期物品 | ContactSensor | 有物品在 7 天内过期 |
| 库存不足 | OccupancySensor | 有商品库存低于最低库存 |

## HomeKit 自动化

在 Home App 中创建自动化：

**临期提醒**
- 当"临期物品"传感器状态变为"打开"
- 发送通知

**库存不足提醒**
- 当"库存不足"传感器状态变为"检测到"
- 发送通知
