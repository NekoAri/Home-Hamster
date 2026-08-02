const { Low } = require('lowdb');
const { JSONFile } = require('lowdb/node');
const path = require('path');
const fs = require('fs');

const DATA_DIR = path.join(__dirname, '..', 'data');
const DB_PATH = path.join(DATA_DIR, 'db.json');

// 确保数据目录存在
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// 默认数据
const defaultData = {
  categories: [
    { id: 1, name: '食品', icon: '🍎', created_at: new Date().toISOString() },
    { id: 2, name: '饮料', icon: '🥤', created_at: new Date().toISOString() },
    { id: 3, name: '日用品', icon: '🧴', created_at: new Date().toISOString() },
    { id: 4, name: '清洁用品', icon: '🧹', created_at: new Date().toISOString() },
    { id: 5, name: '药品', icon: '💊', created_at: new Date().toISOString() },
    { id: 6, name: '零食', icon: '🍫', created_at: new Date().toISOString() },
    { id: 7, name: '调味品', icon: '🧂', created_at: new Date().toISOString() },
    { id: 8, name: '其他', icon: '📦', created_at: new Date().toISOString() },
  ],
  items: [],
  inventory: [],
  consumption_log: [],
};

const adapter = new JSONFile(DB_PATH);
const db = new Low(adapter, defaultData);

// 初始化数据库
async function initDb() {
  await db.read();
  
  // 确保有默认数据
  if (!db.data.categories || db.data.categories.length === 0) {
    db.data.categories = defaultData.categories;
  }
  if (!db.data.items) db.data.items = [];
  if (!db.data.inventory) db.data.inventory = [];
  if (!db.data.consumption_log) db.data.consumption_log = [];
  
  await db.write();
  console.log('✅ 数据库初始化完成:', DB_PATH);
}

// ID 生成器
function nextId(table) {
  const items = db.data[table] || [];
  const maxId = items.reduce((max, item) => Math.max(max, item.id || 0), 0);
  return maxId + 1;
}

// 需要存储为数字类型的字段
const NUM_FIELDS = new Set(['category_id', 'min_stock', 'quantity', 'item_id', 'id'])

// 安全比较：兼容字符串/数字类型的 category_id 和 item_id
function matchId(a, b) {
  return parseInt(a) === parseInt(b)
}

// 兼容 SQLite 的接口
db.prepare = function(sql) {
  // 将多行 SQL 压缩成单行，方便正则匹配
  const sqlNorm = sql.replace(/\s+/g, ' ').trim();
  const sqlLower = sqlNorm.toLowerCase();
  
  return {
    run: async (...params) => {
      const values = params.flat();
      
      // INSERT
      if (sqlLower.startsWith('insert into')) {
        const match = sqlNorm.match(/INSERT INTO (\w+) \(([^)]+)\) VALUES \(([^)]+)\)/i);
        if (match) {
          const table = match[1];
          const columns = match[2].split(',').map(c => c.trim());
          
          const row = { id: nextId(table) };
          columns.forEach((col, i) => {
            const v = values[i];
            if (NUM_FIELDS.has(col) && v != null && v !== '') {
              row[col] = parseInt(v) || parseFloat(v) || v;
            } else {
              row[col] = v;
            }
          });
          
          if (!db.data[table]) db.data[table] = [];
          db.data[table].push(row);
          await db.write();
          return { lastID: row.id, changes: 1 };
        }
      }
      
      // UPDATE
      if (sqlLower.startsWith('update')) {
        const match = sqlNorm.match(/UPDATE (\w+) SET (.+) WHERE (.+)/i);
        if (match) {
          const table = match[1];
          const setClause = match[2];
          const whereClause = match[3];
          
          // 解析 WHERE id = ?
          const idMatch = whereClause.match(/id\s*=\s*\?/i);
          if (idMatch && db.data[table]) {
            const id = parseInt(values[values.length - 1]) || values[values.length - 1];
            const row = db.data[table].find(r => r.id === id);
            if (row) {
              // 解析 SET 子句 (简化处理)
              const setParts = setClause.split(',').map(s => s.trim());
              let valueIndex = 0;
              setParts.forEach(part => {
                const colMatch = part.match(/(\w+)\s*=\s*\?/);
                if (colMatch) {
                  const col = colMatch[1];
                  if (!part.toLowerCase().includes('datetime')) {
                    const val = values[valueIndex++];
                    // 确保数值字段存储为数字类型
                    if (NUM_FIELDS.has(col) && val != null && val !== '') {
                      row[col] = parseInt(val) || parseFloat(val) || val;
                    } else {
                      row[col] = val;
                    }
                  } else {
                    // datetime('now', 'localtime') -> 当前时间
                    row[col] = new Date().toISOString();
                    valueIndex++;
                  }
                }
              });
              await db.write();
              return { lastID: id, changes: 1 };
            }
          }
        }
      }
      
      // DELETE
      if (sqlLower.startsWith('delete')) {
        const match = sqlNorm.match(/DELETE FROM (\w+) WHERE (.+)/i);
        if (match) {
          const table = match[1];
          const whereClause = match[2];
          
          const idMatch = whereClause.match(/id\s*=\s*\?/i);
          if (idMatch && db.data[table]) {
            const id = parseInt(values[0]) || values[0];
            const idx = db.data[table].findIndex(r => r.id === id);
            if (idx >= 0) {
              db.data[table].splice(idx, 1);
              await db.write();
              return { lastID: id, changes: 1 };
            }
          }
        }
      }
      
      return { lastID: 0, changes: 0 };
    },
    
    get: async (...params) => {
      const values = params.flat();
      
      // ── COUNT(*) 聚合查询（用于 overview 统计）──
      if (sqlLower.includes('count(')) {
        // COUNT(*) as count FROM items
        if (/count\(\*\) as count from items/i.test(sqlNorm) && !sqlNorm.includes('JOIN')) {
          return { count: (db.data.items || []).length };
        }
        // COUNT(*) as count FROM categories
        if (/count\(\*\) as count from categories/i.test(sqlNorm)) {
          return { count: (db.data.categories || []).length };
        }
        // COUNT(DISTINCT inv.item_id) — 临期/过期/低库存
        if (/count\(distinct inv\.item_id\)/i.test(sqlNorm)) {
          const now = new Date();
          // 构建 item id 集合，用于过滤已删除商品
          const validItemIds = new Set((db.data.items || []).map(i => parseInt(i.id)));
          // 计算日期范围
          let daysOffset = 0;
          const offsetMatch2 = sqlNorm.match(/\+(\d+) days/i);
          if (offsetMatch2) daysOffset = parseInt(offsetMatch2[1]);
          
          const isExpired = sqlNorm.includes('< date(') || sqlNorm.includes("< date('now'");
          
          let invRows = (db.data.inventory || []).filter(inv => {
            if (!validItemIds.has(parseInt(inv.item_id))) return false;
            if (!inv.expiry_date || !(parseFloat(inv.quantity) > 0)) return false;
            const exp = new Date(inv.expiry_date);
            if (isExpired) {
              return exp < now;
            } else {
              const future = new Date(now.getTime() + daysOffset * 24 * 60 * 60 * 1000);
              return exp >= now && exp <= future;
            }
          });
          const uniqueItems = new Set(invRows.map(r => parseInt(r.item_id)));
          return { count: uniqueItems.size };
        }
        // COUNT(*) 嵌套子查询（低库存）
        if (/count\(\*\) as count from \(/i.test(sqlNorm)) {
          const items = db.data.items || [];
          const inventory = db.data.inventory || [];
          let count = 0;
          items.forEach(item => {
            const invItems = inventory.filter(inv => matchId(inv.item_id, item.id));
            const total = invItems.reduce((s, inv) => s + (parseFloat(inv.quantity) || 0), 0);
            if (total <= parseFloat(item.min_stock)) count++;
          });
          return { count };
        }
        return { count: 0 };
      }
      
      // ── 普通单行查询 ──
      const fromMatch = sqlNorm.match(/FROM (\w+)/i);
      const whereMatch = sqlNorm.match(/WHERE (.+)/i);
      
      if (fromMatch) {
        const table = fromMatch[1].toLowerCase();
        let rows = [...(db.data[table] || [])];
        
        if (whereMatch) {
          const whereClause = whereMatch[1];
          const idMatch = whereClause.match(/(?:i\.|c\.)?id\s*=\s*\?/i);
          if (idMatch) {
            const id = parseInt(values[0]);
            rows = rows.filter(r => r.id === id);
          }
          
          // barcode = ?
          const barcodeMatch = whereClause.match(/barcode\s*=\s*\?/i);
          if (barcodeMatch) {
            rows = rows.filter(r => r.barcode === values[0]);
          }
        }
        
        // 如果是 JOIN 查询，做基本的 category 关联
        if (sqlNorm.includes('JOIN') && rows[0]) {
          const row = { ...rows[0] };
          if (row.category_id != null) {
            const cat = db.data.categories?.find(c => matchId(c.id, row.category_id)) || {};
            row.category_name = cat.name || '';
            row.category_icon = cat.icon || '📦';
          }
          return row;
        }
        
        return rows[0] || null;
      }
      return null;
    },
    
    all: async (...params) => {
      const values = params.flat();
      
      const fromMatch = sqlNorm.match(/FROM (\w+)/i);
      const whereMatch = sqlNorm.match(/WHERE (.+?)(?:\s+GROUP BY|\s+ORDER BY|\s+LIMIT|$)/i);
      const orderMatch = sqlNorm.match(/ORDER BY (.+?)(?:\s+LIMIT|$)/i);
      const limitMatch = sqlNorm.match(/LIMIT (\d+)/i);
      const offsetMatch = sqlNorm.match(/OFFSET (\d+)/i);
      
      if (fromMatch) {
        let rows = [];
        const mainTable = fromMatch[1].toLowerCase();
        
        // ── 专用查询：临期物品（FROM inventory JOIN items ... expiry_date）──
        if (mainTable === 'inventory' && sqlNorm.includes('JOIN') && sqlNorm.includes('expiry_date')) {
          const daysParam = parseInt(values[0]) || 30;
          const now = new Date();
          const future = new Date(now.getTime() + daysParam * 24 * 60 * 60 * 1000);
          // 构建 item id 集合，用于过滤已删除商品
          const validItemIds = new Set((db.data.items || []).map(i => parseInt(i.id)));
          
          rows = (db.data.inventory || [])
            .filter(inv => {
              if (!validItemIds.has(parseInt(inv.item_id))) return false;
              if (!inv.expiry_date || !(parseFloat(inv.quantity) > 0)) return false;
              const exp = new Date(inv.expiry_date);
              return exp <= future; // 包含已过期
            })
            .map(inv => {
              const item = db.data.items?.find(i => matchId(i.id, inv.item_id)) || {};
              const cat = db.data.categories?.find(c => matchId(c.id, item.category_id)) || {};
              const expDate = new Date(inv.expiry_date);
              const msLeft = expDate.getTime() - now.getTime();
              const daysLeft = Math.floor(msLeft / (24 * 60 * 60 * 1000));
              return {
                item_id: inv.item_id,
                name: item.name || '',
                unit: item.unit || '',
                image_path: item.image_path || null,
                category_name: cat.name || '',
                category_icon: cat.icon || '📦',
                inv_id: inv.id,
                quantity: parseFloat(inv.quantity) || 0,
                expiry_date: inv.expiry_date,
                location: inv.location || '',
                days_left: daysLeft,
              };
            })
            .sort((a, b) => new Date(a.expiry_date) - new Date(b.expiry_date));
          
          // LIMIT / OFFSET
          const limit = limitMatch ? parseInt(limitMatch[1]) : rows.length;
          const offset = offsetMatch ? parseInt(offsetMatch[1]) : 0;
          return rows.slice(offset, offset + limit);
        }
        
        // ── 专用查询：by-category（FROM categories LEFT JOIN items ... COUNT）──
        if (mainTable === 'categories' && sqlNorm.includes('COUNT')) {
          rows = (db.data.categories || []).map(cat => {
            const catItems = db.data.items?.filter(i => matchId(i.category_id, cat.id)) || [];
            const itemIds = new Set(catItems.map(i => parseInt(i.id)));
            const totalStock = (db.data.inventory || [])
              .filter(inv => itemIds.has(parseInt(inv.item_id)))
              .reduce((sum, inv) => sum + (parseFloat(inv.quantity) || 0), 0);
            return {
              id: cat.id,
              name: cat.name,
              icon: cat.icon,
              item_count: catItems.length,
              total_stock: totalStock,
            };
          }).sort((a, b) => b.item_count - a.item_count);
          return rows;
        }

        // ── 专用查询：categories（无 COUNT/JOIN，简单列表）──
        if (mainTable === 'categories' && !sqlNorm.includes('JOIN')) {
          rows = [...(db.data.categories || [])];
          // ORDER BY name
          if (orderMatch && orderMatch[1].toLowerCase().includes('name')) {
            rows.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
          }
          return rows;
        }
        
        // ── 专用查询：low-stock（FROM items ... HAVING total_stock）──
        if (mainTable === 'items' && sqlNorm.includes('HAVING')) {
          rows = (db.data.items || []).map(item => {
            const cat = db.data.categories?.find(c => matchId(c.id, item.category_id)) || {};
            const invItems = db.data.inventory?.filter(inv => matchId(inv.item_id, item.id)) || [];
            const total_stock = invItems.reduce((s, inv) => s + (parseFloat(inv.quantity) || 0), 0);
            return {
              ...item,
              category_name: cat.name || '',
              category_icon: cat.icon || '📦',
              total_stock,
            };
          }).filter(item => item.total_stock <= item.min_stock);
          rows.sort((a, b) => a.total_stock - b.total_stock);
          return rows;
        }
        
        // ── 专用查询：consumption_log / trend ──
        if (mainTable === 'consumption_log') {
          const daysParam = parseInt(values[0]) || 30;
          const since = new Date(Date.now() - daysParam * 24 * 60 * 60 * 1000);
          let logs = (db.data.consumption_log || []).filter(cl => new Date(cl.logged_at) >= since);
          
          // item_id 过滤
          if (values[1] !== undefined) {
            const itemId = parseInt(values[1]);
            logs = logs.filter(cl => matchId(cl.item_id, itemId));
          }
          
          // GROUP BY date
          const byDate = {};
          logs.forEach(cl => {
            const d = cl.logged_at ? cl.logged_at.slice(0, 10) : '';
            if (!d) return;
            byDate[d] = (byDate[d] || 0) + (parseFloat(cl.quantity) || 0);
          });
          rows = Object.entries(byDate)
            .map(([date, consumed]) => ({ date, consumed }))
            .sort((a, b) => a.date.localeCompare(b.date));
          return rows;
        }
        
        // ── 通用：FROM items（含 JOIN categories + inventory）──
        if (mainTable === 'items' && sqlNorm.includes('JOIN')) {
          rows = (db.data.items || []).map(item => {
            const newRow = { ...item };
            const cat = db.data.categories?.find(c => matchId(c.id, item.category_id)) || {};
            newRow.category_name = cat.name || '';
            newRow.category_icon = cat.icon || '📦';
            
            if (sqlNorm.includes('SUM(inv.quantity)') || sqlNorm.includes('COALESCE(SUM')) {
              const invItems = db.data.inventory?.filter(inv => matchId(inv.item_id, item.id)) || [];
              newRow.total_stock = invItems.reduce((s, inv) => s + (parseFloat(inv.quantity) || 0), 0);
              const expDates = invItems.map(inv => inv.expiry_date).filter(Boolean).sort();
              newRow.nearest_expiry = expDates[0] || null;
            }
            
            return newRow;
          });
        } else {
          rows = [...(db.data[mainTable] || [])];
        }
        
        // WHERE 过滤（通用）
        if (whereMatch) {
          const whereClause = whereMatch[1];
          const conditions = whereClause.split(/\s+AND\s+/i);
          let paramIdx = 0;
          
          conditions.forEach(cond => {
            // category_id = ?
            if (/category_id\s*=\s*\?/i.test(cond)) {
              const catId = parseInt(values[paramIdx]);
              rows = rows.filter(r => matchId(r.category_id, catId));
              paramIdx++;
            }
            // name/barcode LIKE ?
            else if (/name\s+LIKE\s+\?/i.test(cond)) {
              const pattern = (values[paramIdx] || '').replace(/%/g, '').toLowerCase();
              rows = rows.filter(r => (r.name || '').toLowerCase().includes(pattern));
              paramIdx++;
            }
            else if (/barcode\s+LIKE\s+\?/i.test(cond)) {
              const pattern = (values[paramIdx] || '').replace(/%/g, '').toLowerCase();
              rows = rows.filter(r => (r.barcode || '').toLowerCase().includes(pattern));
              paramIdx++;
            }
            // item_id = ?
            else if (/item_id\s*=\s*\?/i.test(cond)) {
              const itemId = parseInt(values[paramIdx]);
              rows = rows.filter(r => matchId(r.item_id, itemId));
              paramIdx++;
            }
            // id = ?
            else if (/(?:i\.|inv\.)?id\s*=\s*\?/i.test(cond)) {
              const id = parseInt(values[paramIdx]);
              rows = rows.filter(r => matchId(r.id, id) || matchId(r.item_id, id));
              paramIdx++;
            }
          });
        }
        
        // ORDER BY
        if (orderMatch) {
          const orderParts = orderMatch[1].trim().split(/\s+/);
          const field = orderParts[0].replace(/\w+\./g, '');
          const desc = (orderParts[1] || '').toLowerCase() === 'desc';
          rows.sort((a, b) => {
            let aVal = a[field], bVal = b[field];
            if (aVal == null) return 1;
            if (bVal == null) return -1;
            if (field.includes('date') || field.includes('_at')) {
              aVal = new Date(aVal).getTime();
              bVal = new Date(bVal).getTime();
            }
            if (desc) return bVal > aVal ? 1 : -1;
            return aVal > bVal ? 1 : -1;
          });
        }
        
        // LIMIT / OFFSET
        const limit = limitMatch ? parseInt(limitMatch[1]) : rows.length;
        const offset = offsetMatch ? parseInt(offsetMatch[1]) : 0;
        return rows.slice(offset, offset + limit);
      }
      
      return [];
    }
  };
};

// 初始化
db.init = initDb;

module.exports = db;
