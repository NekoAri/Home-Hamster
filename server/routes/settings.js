const express = require('express');
const router = express.Router();
const path = require('path');
const fs = require('fs');

const CONFIG_PATH = path.join(__dirname, '..', 'data', 'config.json');
const DATA_DIR = path.join(__dirname, '..', 'data');

// 确保目录存在
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

// 读取配置
function readConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    }
  } catch (e) {
    console.error('读取配置失败:', e.message);
  }
  return {};
}

// 保存配置
function writeConfig(config) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');
}

// 获取数据库配置（隐藏密码）
router.get('/database', (req, res) => {
  const config = readConfig();
  const dbConfig = config.database || {};
  res.json({
    success: true,
    data: {
      type: dbConfig.type || 'json', // json | sqlite
      sqlitePath: dbConfig.sqlitePath || '',
      hasPassword: !!(dbConfig.sqlitePassword),
    }
  });
});

// 保存数据库配置
router.put('/database', async (req, res) => {
  try {
    const { type, sqlitePath, sqlitePassword } = req.body;
    const config = readConfig();

    if (type === 'sqlite') {
      if (!sqlitePath) {
        return res.json({ success: false, message: '请填写数据库路径' });
      }
      // 验证路径是否存在
      if (!fs.existsSync(sqlitePath)) {
        // 尝试创建父目录
        const parentDir = path.dirname(sqlitePath);
        if (parentDir && !fs.existsSync(parentDir)) {
          try {
            fs.mkdirSync(parentDir, { recursive: true });
          } catch (e) {
            return res.json({ success: false, message: '目录创建失败: ' + e.message });
          }
        }
      }

      config.database = {
        type: 'sqlite',
        sqlitePath,
        sqlitePassword: sqlitePassword || '',
      };
    } else {
      // 切换回 JSON
      config.database = { type: 'json' };
    }

    writeConfig(config);
    res.json({ success: true, message: '保存成功，重启服务后生效' });
  } catch (e) {
    res.json({ success: false, message: '保存失败: ' + e.message });
  }
});

// 测试数据库连接
router.post('/database/test', async (req, res) => {
  try {
    const { type, sqlitePath, sqlitePassword } = req.body;

    if (type === 'sqlite') {
      if (!sqlitePath) {
        return res.json({ success: false, message: '请填写数据库路径' });
      }

      const initSQLiteDatabase = require('../db/sqlite-adapter');
      const testDb = await initSQLiteDatabase(sqlitePath, sqlitePassword);
      // 尝试一个简单查询
      testDb.prepare('SELECT 1 as ok').get();
      testDb.close();
      res.json({ success: true, message: '连接成功！' });
    } else {
      res.json({ success: true, message: 'JSON 模式无需测试' });
    }
  } catch (e) {
    res.json({ success: false, message: '连接失败: ' + e.message });
  }
});

module.exports = router;
