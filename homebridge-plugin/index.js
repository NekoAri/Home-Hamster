const http = require('http');

// Homebridge 平台插件
class HomeInventoryPlatform {
  constructor(log, config, api) {
    this.log = log;
    this.config = config;
    this.api = api;
    this.Service = api.hap.Service;
    this.Characteristic = api.hap.Characteristic;

    this.serverUrl = config.serverUrl || 'http://localhost:3000';
    this.checkInterval = config.checkInterval || 60; // 秒
    this.expiringDays = config.expiringDays || 7; // 临期天数

    this.expiringSensor = null;
    this.lowStockSensor = null;

    this.log('家庭仓库插件已初始化');

    if (api) {
      api.on('didFinishLaunching', () => {
        this.discoverDevices();
        this.startPolling();
      });
    }
  }

  // 创建设备
  discoverDevices() {
    const uuid = this.api.hap.uuid;

    // 临期传感器（ContactSensor）
    const expiringUUID = uuid.generate('home-inventory-expiring');
    this.expiringSensor = new this.Service.ContactSensor('临期物品', expiringUUID);
    this.expiringSensor
      .setCharacteristic(this.Characteristic.Manufacturer, 'Home Inventory')
      .setCharacteristic(this.Characteristic.Model, 'Expiring Sensor')
      .setCharacteristic(this.Characteristic.SerialNumber, 'EXP-001');

    // 低库存传感器（OccupancySensor）
    const lowStockUUID = uuid.generate('home-inventory-lowstock');
    this.lowStockSensor = new this.Service.OccupancySensor('库存不足', lowStockUUID);
    this.lowStockSensor
      .setCharacteristic(this.Characteristic.Manufacturer, 'Home Inventory')
      .setCharacteristic(this.Characteristic.Model, 'Low Stock Sensor')
      .setCharacteristic(this.Characteristic.SerialNumber, 'LOW-001');

    this.log('已创建传感器：临期物品、库存不足');
  }

  // 轮询检查
  startPolling() {
    this.checkStatus();
    setInterval(() => this.checkStatus(), this.checkInterval * 1000);
  }

  // 检查库存状态
  checkStatus() {
    const options = {
      hostname: new URL(this.serverUrl).hostname,
      port: new URL(this.serverUrl).port || 80,
      path: '/api/stats/homekit',
      method: 'GET',
      timeout: 5000
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.success) {
            this.updateSensors(result.data);
          }
        } catch (e) {
          this.log('解析响应失败:', e.message);
        }
      });
    });

    req.on('error', (e) => {
      this.log('请求失败:', e.message);
    });

    req.on('timeout', () => {
      req.destroy();
      this.log('请求超时');
    });

    req.end();
  }

  // 更新传感器状态
  updateSensors(data) {
    // 临期传感器：有临期物品时 CONTACT_DETECTED = 0 (打开状态)
    const expiringDetected = data.expiring.triggered ? 
      this.Characteristic.ContactSensorState.CONTACT_NOT_DETECTED : 
      this.Characteristic.ContactSensorState.CONTACT_DETECTED;
    
    this.expiringSensor.setCharacteristic(
      this.Characteristic.ContactSensorState,
      expiringDetected
    );

    // 低库存传感器：有低库存时 OCCUPANCY_DETECTED = 1
    const lowStockDetected = data.lowStock.triggered ?
      this.Characteristic.OccupancyDetected.OCCUPANCY_DETECTED :
      this.Characteristic.OccupancyDetected.OCCUPANCY_NOT_DETECTED;

    this.lowStockSensor.setCharacteristic(
      this.Characteristic.OccupancyDetected,
      lowStockDetected
    );

    // 记录日志
    if (data.expiring.triggered) {
      this.log(`⚠️ 发现 ${data.expiring.count} 个临期物品`);
    }
    if (data.lowStock.triggered) {
      this.log(`📉 发现 ${data.lowStock.count} 个库存不足物品`);
    }
  }

  // Homebridge 要求的 accessories 方法
  accessories(callback) {
    const accessories = [];

    if (this.expiringSensor) {
      const expiringAccessory = new this.api.platformAccessory('临期物品', this.api.hap.uuid.generate('home-inventory-expiring'));
      expiringAccessory.addService(this.expiringSensor);
      accessories.push(expiringAccessory);
    }

    if (this.lowStockSensor) {
      const lowStockAccessory = new this.api.platformAccessory('库存不足', this.api.hap.uuid.generate('home-inventory-lowstock'));
      lowStockAccessory.addService(this.lowStockSensor);
      accessories.push(lowStockAccessory);
    }

    callback(accessories);
  }
}

// 导出插件
module.exports = (api) => {
  api.registerPlatform('homebridge-home-inventory', 'HomeInventory', HomeInventoryPlatform);
};
