/**
 * SQLite 适配器 - 使用 sql.js 连接外部 SQLite 数据库
 * 实现与 schema.js (lowdb) 相同的 prepare/run/get/all 接口
 * 
 * 支持的功能：
 * - 自动建表（如果表不存在）
 * - 所有现有路由无需修改即可使用
 */

const initSqlJs = require('sql.js');
const fs = require('fs');
const path = require('path');

let SQL = null;

// 默认数据
const DEFAULT_CATEGORIES = [
  { id: 1, name: '食品', icon: '🍎' },
  { id: 2, name: '饮料', icon: '🥤' },
  { id: 3, name: '日用品', icon: '🧴' },
  { id: 4, name: '清洁用品', icon: '🧹' },
  { id: 5, name: '药品', icon: '💊' },
  { id: 6, name: '零食', icon: '🍫' },
  { id: 7, name: '调味品', icon: '🧂' },
  { id: 8, name: '其他', icon: '📦' },
];

const CREATE_TABLES = `
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  icon TEXT DEFAULT '📦',
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  barcode TEXT DEFAULT '',
  category_id INTEGER DEFAULT NULL,
  image_path TEXT DEFAULT '',
  unit TEXT DEFAULT '个',
  min_stock INTEGER DEFAULT 0,
  notes TEXT DEFAULT NULL,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  quantity REAL DEFAULT 0,
  production_date TEXT DEFAULT NULL,
  expiry_date TEXT DEFAULT NULL,
  location TEXT DEFAULT '',
  notes TEXT DEFAULT NULL,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS consumption_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  quantity REAL DEFAULT 0,
  notes TEXT DEFAULT NULL,
  logged_at TEXT DEFAULT (datetime('now', 'localtime'))
);
`;

/**
 * 初始化 SQLite 数据库连接
 * @param {string} dbPath - SQLite 数据库文件路径
 * @param {string} [password] - 可选密码
 * @returns {Object} 数据库对象，接口兼容 schema.js
 */
async function initSQLiteDatabase(dbPath, password) {
  // 延迟加载 sql.js WASM
  if (!SQL) {
    SQL = await initSqlJs();
  }

  let db;
  const isNew = !fs.existsSync(dbPath);

  if (isNew) {
    db = new SQL.Database();
  } else {
    const fileBuffer = fs.readFileSync(dbPath);
    db = new SQL.Database(fileBuffer);
  }

  // 创建表结构
  db.run(CREATE_TABLES);

  // 如果是新数据库，插入默认分类
  if (isNew) {
    const catCheck = db.exec('SELECT COUNT(*) as cnt FROM categories');
    if (catCheck.length > 0 && catCheck[0].values[0][0] === 0) {
      DEFAULT_CATEGORIES.forEach(cat => {
        db.run('INSERT INTO categories (id, name, icon) VALUES (?, ?, ?)', [cat.id, cat.name, cat.icon]);
      });
    }
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(dbPath, buffer);
  }

  const dbObj = {
    _sqlDb: db,
    _dbPath: dbPath,
  };

  // 自动保存到文件
  dbObj._save = function() {
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(dbPath, buffer);
  };

  // 兼容接口：prepare(sql)
  dbObj.prepare = function(sql) {
    return {
      run: async (...params) => {
        const values = params.flat();
        try {
          db.run(sql, values);
          dbObj._save();
          const lastResult = db.exec('SELECT last_insert_rowid() as lid');
          const lastID = lastResult.length > 0 ? lastResult[0].values[0][0] : 0;
          return { lastID, changes: db.getRowsModified() };
        } catch (e) {
          console.error('SQL run error:', sql, values, e.message);
          return { lastID: 0, changes: 0 };
        }
      },

      get: async (...params) => {
        const values = params.flat();
        try {
          const stmt = db.prepare(sql);
          stmt.bind(values);
          if (stmt.step()) {
            const row = stmt.getAsObject();
            stmt.free();
            return row;
          }
          stmt.free();
          return null;
        } catch (e) {
          console.error('SQL get error:', sql, values, e.message);
          return null;
        }
      },

      all: async (...params) => {
        const values = params.flat();
        try {
          const stmt = db.prepare(sql);
          stmt.bind(values);
          const rows = [];
          while (stmt.step()) {
            rows.push(stmt.getAsObject());
          }
          stmt.free();
          return rows;
        } catch (e) {
          console.error('SQL all error:', sql, values, e.message);
          return [];
        }
      },
    };
  };

  // 初始化函数（兼容）
  dbObj.init = async function() {
    console.log('✅ SQLite 数据库已加载:', dbPath);
  };

  // 关闭数据库
  dbObj.close = function() {
    try {
      db.close();
    } catch (e) {
      // ignore
    }
  };

  return dbObj;
}

module.exports = initSQLiteDatabase;
