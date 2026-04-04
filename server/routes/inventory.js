const express = require('express');
const router = express.Router();

// GET /api/inventory - 获取所有库存（可过滤）
router.get('/', async (req, res) => {
  try {
    const db = req.db;
    const { item_id, expiring_days, low_stock } = req.query;
    let where = '1=1';
    const params = [];

    if (item_id) {
      where += ` AND inv.item_id = ?`;
      params.push(item_id);
    }
    if (expiring_days) {
      where += ` AND inv.expiry_date IS NOT NULL 
                 AND date(inv.expiry_date) <= date('now', '+' || ? || ' days', 'localtime')
                 AND date(inv.expiry_date) >= date('now', 'localtime')
                 AND inv.quantity > 0`;
      params.push(expiring_days);
    }
    if (low_stock === 'true') {
      where += ` AND inv.quantity <= i.min_stock`;
    }

    const records = await db.prepare(`
      SELECT inv.*, i.name as item_name, i.unit, i.min_stock,
             c.name as category_name, c.icon as category_icon,
             i.image_path
      FROM inventory inv
      JOIN items i ON i.id = inv.item_id
      LEFT JOIN categories c ON c.id = i.category_id
      WHERE ${where}
      ORDER BY inv.expiry_date ASC
    `).all(...params);

    res.json({ success: true, data: records });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// POST /api/inventory - 添加库存批次
router.post('/', async (req, res) => {
  try {
    const db = req.db;
    const { item_id, quantity, production_date, expiry_date, location, notes } = req.body;
    if (!item_id || quantity === undefined) {
      return res.status(400).json({ success: false, message: 'item_id 和 quantity 不能为空' });
    }

    const item = await db.prepare(`SELECT * FROM items WHERE id = ?`).get(item_id);
    if (!item) return res.status(404).json({ success: false, message: '商品不存在' });

    const result = await db.prepare(`
      INSERT INTO inventory (item_id, quantity, production_date, expiry_date, location, notes)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(item_id, quantity, production_date || null, expiry_date || null, location || '默认位置', notes || null);

    // 更新商品的 updated_at
    await db.prepare(`UPDATE items SET updated_at = datetime('now', 'localtime') WHERE id = ?`).run(item_id);

    const record = await db.prepare(`SELECT * FROM inventory WHERE id = ?`).get(result.lastID);
    res.status(201).json({ success: true, data: record });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// PUT /api/inventory/:id - 更新库存批次
router.put('/:id', async (req, res) => {
  try {
    const db = req.db;
    const record = await db.prepare(`SELECT * FROM inventory WHERE id = ?`).get(req.params.id);
    if (!record) return res.status(404).json({ success: false, message: '库存记录不存在' });

    const { quantity, production_date, expiry_date, location, notes } = req.body;

    await db.prepare(`
      UPDATE inventory SET
        quantity = ?, production_date = ?, expiry_date = ?,
        location = ?, notes = ?,
        updated_at = datetime('now', 'localtime')
      WHERE id = ?
    `).run(
      quantity ?? record.quantity,
      production_date ?? record.production_date,
      expiry_date ?? record.expiry_date,
      location ?? record.location,
      notes ?? record.notes,
      req.params.id
    );

    // 记录消耗
    const diff = record.quantity - (quantity ?? record.quantity);
    if (diff > 0) {
      await db.prepare(`
        INSERT INTO consumption_log (item_id, quantity, notes)
        VALUES (?, ?, ?)
      `).run(record.item_id, diff, '手动调整');
    }

    const updated = await db.prepare(`SELECT * FROM inventory WHERE id = ?`).get(req.params.id);
    res.json({ success: true, data: updated });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// DELETE /api/inventory/:id - 删除库存批次
router.delete('/:id', async (req, res) => {
  try {
    const db = req.db;
    await db.prepare(`DELETE FROM inventory WHERE id = ?`).run(req.params.id);
    res.json({ success: true, message: '删除成功' });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// POST /api/inventory/:id/consume - 消耗库存
router.post('/:id/consume', async (req, res) => {
  try {
    const db = req.db;
    const { quantity, notes } = req.body;
    if (!quantity || quantity <= 0) {
      return res.status(400).json({ success: false, message: '消耗数量必须大于0' });
    }

    const record = await db.prepare(`SELECT * FROM inventory WHERE id = ?`).get(req.params.id);
    if (!record) return res.status(404).json({ success: false, message: '库存记录不存在' });
    if (record.quantity < quantity) {
      return res.status(400).json({ success: false, message: `库存不足，当前剩余 ${record.quantity}` });
    }

    const newQty = record.quantity - quantity;
    await db.prepare(`
      UPDATE inventory SET quantity = ?, updated_at = datetime('now', 'localtime') WHERE id = ?
    `).run(newQty, req.params.id);

    await db.prepare(`
      INSERT INTO consumption_log (item_id, quantity, notes) VALUES (?, ?, ?)
    `).run(record.item_id, quantity, notes || '正常消耗');

    res.json({ success: true, data: { remaining: newQty } });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

module.exports = router;
