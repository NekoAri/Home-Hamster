const express = require('express');
const router = express.Router();

// GET /api/stats/overview - 仪表盘概览
router.get('/overview', async (req, res) => {
  try {
    const db = req.db;
    const totalItemsRow = await db.prepare(`SELECT COUNT(*) as count FROM items`).get();
    const totalCategoriesRow = await db.prepare(`SELECT COUNT(*) as count FROM categories`).get();
    
    // 临期物品（30天内）
    const expiringSoonRow = await db.prepare(`
      SELECT COUNT(DISTINCT inv.item_id) as count
      FROM inventory inv
      WHERE inv.expiry_date IS NOT NULL
        AND date(inv.expiry_date) <= date('now', '+30 days', 'localtime')
        AND date(inv.expiry_date) >= date('now', 'localtime')
        AND inv.quantity > 0
    `).get();

    // 库存不足物品
    const lowStockRow = await db.prepare(`
      SELECT COUNT(*) as count FROM (
        SELECT i.id
        FROM items i
        JOIN (SELECT item_id, SUM(quantity) as total FROM inventory GROUP BY item_id) s
          ON s.item_id = i.id
        WHERE s.total <= i.min_stock
      )
    `).get();

    // 已过期物品
    const expiredRow = await db.prepare(`
      SELECT COUNT(DISTINCT inv.item_id) as count
      FROM inventory inv
      WHERE inv.expiry_date IS NOT NULL
        AND date(inv.expiry_date) < date('now', 'localtime')
        AND inv.quantity > 0
    `).get();

    res.json({
      success: true,
      data: {
        totalItems: totalItemsRow.count,
        totalCategories: totalCategoriesRow.count,
        expiringSoon: expiringSoonRow.count,
        lowStock: lowStockRow.count,
        expired: expiredRow.count
      }
    });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/expiring - 临期 & 过期物品列表
router.get('/expiring', async (req, res) => {
  try {
    const db = req.db;
    const days = req.query.days || 30;
    const items = await db.prepare(`
      SELECT 
        i.id as item_id, i.name, i.unit, i.image_path,
        c.name as category_name, c.icon as category_icon,
        inv.id as inv_id, inv.quantity, inv.expiry_date, inv.location,
        CAST(julianday(inv.expiry_date) - julianday('now') AS INTEGER) as days_left
      FROM inventory inv
      JOIN items i ON i.id = inv.item_id
      LEFT JOIN categories c ON c.id = i.category_id
      WHERE inv.expiry_date IS NOT NULL
        AND date(inv.expiry_date) <= date('now', '+' || ? || ' days', 'localtime')
        AND inv.quantity > 0
      ORDER BY inv.expiry_date ASC
    `).all(days);

    res.json({ success: true, data: items });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/low-stock - 库存不足列表
router.get('/low-stock', async (req, res) => {
  try {
    const db = req.db;
    const items = await db.prepare(`
      SELECT 
        i.id, i.name, i.unit, i.min_stock, i.image_path,
        c.name as category_name, c.icon as category_icon,
        COALESCE(SUM(inv.quantity), 0) as total_stock
      FROM items i
      LEFT JOIN categories c ON c.id = i.category_id
      LEFT JOIN inventory inv ON inv.item_id = i.id
      GROUP BY i.id
      HAVING total_stock <= i.min_stock
      ORDER BY total_stock ASC
    `).all();

    res.json({ success: true, data: items });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/by-category - 按分类统计
router.get('/by-category', async (req, res) => {
  try {
    const db = req.db;
    const data = await db.prepare(`
      SELECT 
        c.id, c.name, c.icon,
        COUNT(DISTINCT i.id) as item_count,
        COALESCE(SUM(inv.quantity), 0) as total_stock
      FROM categories c
      LEFT JOIN items i ON i.category_id = c.id
      LEFT JOIN inventory inv ON inv.item_id = i.id
      GROUP BY c.id
      ORDER BY item_count DESC
    `).all();

    res.json({ success: true, data });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/consumption - 消耗趋势（最近N天）
router.get('/consumption', async (req, res) => {
  try {
    const db = req.db;
    const days = req.query.days || 30;
    const itemId = req.query.item_id;

    let where = `WHERE date(cl.logged_at) >= date('now', '-' || ? || ' days', 'localtime')`;
    const params = [days];
    if (itemId) {
      where += ` AND cl.item_id = ?`;
      params.push(itemId);
    }

    const trend = await db.prepare(`
      SELECT 
        date(cl.logged_at) as date,
        SUM(cl.quantity) as consumed
      FROM consumption_log cl
      ${where}
      GROUP BY date(cl.logged_at)
      ORDER BY date ASC
    `).all(...params);

    res.json({ success: true, data: trend });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/suggestions - 补货建议
router.get('/suggestions', async (req, res) => {
  try {
    const db = req.db;
    // 计算平均每日消耗量，并预测补货时间
    const suggestions = await db.prepare(`
      WITH daily_avg AS (
        SELECT 
          item_id,
          SUM(quantity) * 1.0 / MAX(
            julianday('now') - julianday(MIN(logged_at)) + 1, 1
          ) as avg_daily_consumption
        FROM consumption_log
        WHERE logged_at >= date('now', '-30 days', 'localtime')
        GROUP BY item_id
      ),
      stock_total AS (
        SELECT item_id, SUM(quantity) as total_stock
        FROM inventory
        GROUP BY item_id
      )
      SELECT 
        i.id, i.name, i.unit, i.min_stock, i.image_path,
        c.name as category_name, c.icon as category_icon,
        COALESCE(st.total_stock, 0) as total_stock,
        ROUND(COALESCE(da.avg_daily_consumption, 0), 2) as avg_daily,
        CASE 
          WHEN da.avg_daily_consumption > 0 
          THEN ROUND(COALESCE(st.total_stock, 0) / da.avg_daily_consumption)
          ELSE NULL
        END as days_remaining,
        CASE
          WHEN COALESCE(st.total_stock, 0) <= i.min_stock THEN 'urgent'
          WHEN da.avg_daily_consumption > 0 
            AND COALESCE(st.total_stock, 0) / da.avg_daily_consumption <= 7 THEN 'soon'
          ELSE 'ok'
        END as status
      FROM items i
      LEFT JOIN categories c ON c.id = i.category_id
      LEFT JOIN daily_avg da ON da.item_id = i.id
      LEFT JOIN stock_total st ON st.item_id = i.id
      WHERE status IN ('urgent', 'soon')
      ORDER BY CASE status WHEN 'urgent' THEN 0 ELSE 1 END, days_remaining ASC
    `).all();

    res.json({ success: true, data: suggestions });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/stats/homekit - Homebridge 插件专用接口
router.get('/homekit', async (req, res) => {
  try {
    const db = req.db;
    // 临期物品（7天内）
    const expiringItems = await db.prepare(`
      SELECT i.name, inv.expiry_date, inv.quantity,
             CAST(julianday(inv.expiry_date) - julianday('now') AS INTEGER) as days_left
      FROM inventory inv
      JOIN items i ON i.id = inv.item_id
      WHERE inv.expiry_date IS NOT NULL
        AND date(inv.expiry_date) <= date('now', '+7 days', 'localtime')
        AND date(inv.expiry_date) >= date('now', 'localtime')
        AND inv.quantity > 0
      ORDER BY inv.expiry_date ASC
    `).all();

    // 库存不足物品
    const lowStockItems = await db.prepare(`
      SELECT i.name, i.min_stock, COALESCE(SUM(inv.quantity), 0) as total_stock
      FROM items i
      LEFT JOIN inventory inv ON inv.item_id = i.id
      GROUP BY i.id
      HAVING total_stock <= i.min_stock
    `).all();

    res.json({
      success: true,
      data: {
        expiring: {
          triggered: expiringItems.length > 0,
          count: expiringItems.length,
          items: expiringItems
        },
        lowStock: {
          triggered: lowStockItems.length > 0,
          count: lowStockItems.length,
          items: lowStockItems
        }
      }
    });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

module.exports = router;
