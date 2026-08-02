const express = require('express');
const router = express.Router();

// GET /api/categories - 获取所有分类
router.get('/', async (req, res) => {
  try {
    const db = req.db;
    const categories = await db.prepare(`
      SELECT c.*, COUNT(i.id) as item_count
      FROM categories c
      LEFT JOIN items i ON i.category_id = c.id
      GROUP BY c.id
      ORDER BY c.name
    `).all();
    res.json({ success: true, data: categories });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// POST /api/categories - 新建分类
router.post('/', async (req, res) => {
  try {
    const db = req.db;
    const { name, icon = '📦' } = req.body;
    if (!name) return res.status(400).json({ success: false, message: '分类名称不能为空' });
    
    const result = await db.prepare(
      `INSERT INTO categories (name, icon) VALUES (?, ?)`
    ).run(name, icon);
    
    const category = await db.prepare(`SELECT * FROM categories WHERE id = ?`).get(result.lastID);
    res.status(201).json({ success: true, data: category });
  } catch (e) {
    if (e.message.includes('UNIQUE')) {
      return res.status(409).json({ success: false, message: '分类名称已存在' });
    }
    res.status(500).json({ success: false, message: e.message });
  }
});

// PUT /api/categories/:id - 修改分类
router.put('/:id', async (req, res) => {
  try {
    const db = req.db;
    const { name, icon } = req.body;
    const fields = [];
    const values = [];
    if (name) { fields.push('name = ?'); values.push(name); }
    if (icon) { fields.push('icon = ?'); values.push(icon); }
    if (!fields.length) return res.status(400).json({ success: false, message: '无可更新字段' });
    values.push(req.params.id);
    
    await db.prepare(`UPDATE categories SET ${fields.join(', ')} WHERE id = ?`).run(...values);
    const category = await db.prepare(`SELECT * FROM categories WHERE id = ?`).get(req.params.id);
    res.json({ success: true, data: category });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// DELETE /api/categories/:id - 删除分类
router.delete('/:id', async (req, res) => {
  try {
    const db = req.db;
    await db.prepare(`DELETE FROM categories WHERE id = ?`).run(req.params.id);
    res.json({ success: true, message: '删除成功' });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

module.exports = router;
