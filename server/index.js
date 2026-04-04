const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const http = require('http');
const https = require('https');
const os = require('os');

const app = express();
const HTTP_PORT  = process.env.PORT       || 3000;
const HTTPS_PORT = process.env.HTTPS_PORT || 3443;

// 中间件
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// 初始化数据库
async function initDatabase() {
  const CONFIG_PATH = path.join(__dirname, 'data', 'config.json');
  let dbConfig = { type: 'json' };
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
      if (config.database && config.database.type) {
        dbConfig = config.database;
      }
    }
  } catch (e) {
    console.warn('⚠️  读取配置失败，使用默认 JSON 数据库');
  }

  let db;
  if (dbConfig.type === 'sqlite' && dbConfig.sqlitePath) {
    try {
      const initSQLiteDatabase = require('./db/sqlite-adapter');
      db = await initSQLiteDatabase(dbConfig.sqlitePath, dbConfig.sqlitePassword);
      console.log(`📦 使用 SQLite 数据库: ${dbConfig.sqlitePath}`);
    } catch (e) {
      console.error('❌ SQLite 初始化失败，回退到 JSON 数据库:', e.message);
      db = require('./db/schema');
    }
  } else {
    db = require('./db/schema');
    console.log('📦 使用 JSON 文件数据库（默认）');
  }
  await db.init();
  return db;
}

// 将 db 注入到 req.db
const dbMiddleware = (db) => (req, res, next) => {
  req.db = db;
  next();
};

// 获取本机局域网 IP
function getLocalIPs() {
  const nets = os.networkInterfaces();
  const ips = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) ips.push(net.address);
    }
  }
  return ips;
}

// 启动服务
async function start() {
  const db = await initDatabase();
  app.locals.db = db;

  // 注册 db 中间件（在路由之前）
  app.use('/api', dbMiddleware(db));

  // API 路由（必须在静态文件之前，防止 SPA fallback 拦截）
  app.use('/api/settings',   require('./routes/settings'));
  app.use('/api/categories', require('./routes/categories'));
  app.use('/api/items',      require('./routes/items'));
  app.use('/api/inventory',  require('./routes/inventory'));
  app.use('/api/stats',      require('./routes/stats'));

  // 健康检查
  app.get('/api/health', (req, res) => {
    res.json({ success: true, message: '家庭仓库管理系统运行中 🏠', time: new Date().toISOString() });
  });

  // 静态文件：上传的图片
  app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

  // 静态文件：前端页面
  app.use(express.static(path.join(__dirname, '..', 'client', 'dist')));

  // SPA fallback（前端路由）
  app.get('*', (req, res) => {
    const indexPath = path.join(__dirname, '..', 'client', 'dist', 'index.html');
    if (fs.existsSync(indexPath)) {
      res.sendFile(indexPath);
    } else {
      res.json({ success: true, message: '后端服务正常，前端尚未构建' });
    }
  });

  // 错误处理
  app.use((err, req, res, next) => {
    console.error('❌ 错误:', err.message);
    res.status(err.status || 500).json({ success: false, message: err.message || '服务器内部错误' });
  });

  // 启动 HTTP 服务
  http.createServer(app).listen(HTTP_PORT, '0.0.0.0', () => {
    console.log(`🌐 HTTP  服务: http://localhost:${HTTP_PORT}`);
  });

  // 启动 HTTPS 服务（如果证书存在）
  const keyPath  = path.join(__dirname, 'certs', 'key.pem');
  const certPath = path.join(__dirname, 'certs', 'cert.pem');

  if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
    const sslOptions = {
      key:  fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    };

    https.createServer(sslOptions, app).listen(HTTPS_PORT, '0.0.0.0', () => {
      const ips = getLocalIPs();
      console.log('');
      console.log(`🚀 家庭仓库管理系统启动成功！`);
      console.log(`🔒 HTTPS 服务（摄像头扫码用这个）：`);
      ips.forEach(ip => console.log(`   https://${ip}:${HTTPS_PORT}`));
      console.log(`   https://localhost:${HTTPS_PORT}`);
      console.log('');
      console.log(`⚠️  首次用手机访问时会提示"证书不受信任"，点击继续访问即可`);
    });
  } else {
    console.log('⚠️  未找到 SSL 证书，仅启动 HTTP 服务');
    console.log('   运行 node gen-cert.js 生成证书后重启可启用 HTTPS');
  }
}

start();

module.exports = app;
