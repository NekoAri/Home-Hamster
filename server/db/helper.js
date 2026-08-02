/**
 * 数据库路由辅助模块
 * 让路由文件可以通过 req.app.locals.db 动态获取数据库实例
 * 兼容 lowdb (JSON) 和 sql.js (SQLite) 两种后端
 */

/**
 * 从 Express 请求对象获取数据库实例
 * 用法: const db = getDb(req);
 */
function getDb(req) {
  return req.app.locals.db;
}

/**
 * 获取数据库配置信息
 * 用法: const info = getDbInfo(req);
 */
function getDbInfo(req) {
  const db = req.app.locals.db;
  if (db._dbPath && db._sqlDb) {
    return { type: 'sqlite', path: db._dbPath };
  }
  return { type: 'json', path: path.join(__dirname, '..', 'data', 'db.json') };
}

module.exports = { getDb };
