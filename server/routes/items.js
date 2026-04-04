const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const fs = require('fs');

// 图片上传配置
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, '..', 'uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    cb(null, `item_${Date.now()}${ext}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('image/')) cb(null, true);
    else cb(new Error('只允许上传图片'));
  }
});

// GET /api/items - 获取商品列表（支持搜索、分类过滤）
router.get('/', async (req, res) => {
  try {
    const db = req.db;
    const { search, category_id, page = 1, limit = 20 } = req.query;
    const offset = (page - 1) * limit;

    let where = '1=1';
    const params = [];
    if (search) {
      where += ` AND (i.name LIKE ? OR i.barcode LIKE ?)`;
      params.push(`%${search}%`, `%${search}%`);
    }
    if (category_id) {
      where += ` AND i.category_id = ?`;
      params.push(category_id);
    }

    const items = await db.prepare(`
      SELECT 
        i.*,
        c.name as category_name,
        c.icon as category_icon,
        COALESCE(SUM(inv.quantity), 0) as total_stock,
        MIN(inv.expiry_date) as nearest_expiry
      FROM items i
      LEFT JOIN categories c ON c.id = i.category_id
      LEFT JOIN inventory inv ON inv.item_id = i.id
      WHERE ${where}
      GROUP BY i.id
      ORDER BY i.updated_at DESC
      LIMIT ? OFFSET ?
    `).all(...params, limit, offset);

    const totalRow = await db.prepare(`
      SELECT COUNT(DISTINCT i.id) as count FROM items i WHERE ${where}
    `).get(...params);

    res.json({ success: true, data: items, total: totalRow.count, page: +page, limit: +limit });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/items/:id - 获取商品详情（含所有库存批次）
router.get('/:id', async (req, res) => {
  try {
    const db = req.db;
    const item = await db.prepare(`
      SELECT i.*, c.name as category_name, c.icon as category_icon
      FROM items i
      LEFT JOIN categories c ON c.id = i.category_id
      WHERE i.id = ?
    `).get(req.params.id);

    if (!item) return res.status(404).json({ success: false, message: '商品不存在' });

    const inventory = await db.prepare(`
      SELECT * FROM inventory WHERE item_id = ? ORDER BY expiry_date ASC
    `).all(req.params.id);

    item.inventory = inventory;
    item.total_stock = inventory.reduce((sum, r) => sum + r.quantity, 0);

    res.json({ success: true, data: item });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// GET /api/items/barcode/:barcode - 通过条码查商品
router.get('/barcode/:barcode', async (req, res) => {
  try {
    const db = req.db;
    const item = await db.prepare(`
      SELECT i.*, c.name as category_name, c.icon as category_icon,
             COALESCE(SUM(inv.quantity), 0) as total_stock
      FROM items i
      LEFT JOIN categories c ON c.id = i.category_id
      LEFT JOIN inventory inv ON inv.item_id = i.id
      WHERE i.barcode = ?
      GROUP BY i.id
    `).get(req.params.barcode);

    if (!item) return res.status(404).json({ success: false, message: '未找到对应商品' });
    res.json({ success: true, data: item });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// POST /api/items - 新建商品
router.post('/', upload.single('image'), async (req, res) => {
  try {
    const db = req.db;
    const { name, barcode, category_id, unit = '个', min_stock = 1, notes } = req.body;
    if (!name) return res.status(400).json({ success: false, message: '商品名称不能为空' });

    const image_path = req.file ? `/uploads/${req.file.filename}` : null;

    const result = await db.prepare(`
      INSERT INTO items (name, barcode, category_id, image_path, unit, min_stock, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(name, barcode || null, category_id || null, image_path, unit, min_stock, notes || null);

    const item = await db.prepare(`SELECT * FROM items WHERE id = ?`).get(result.lastID);
    res.status(201).json({ success: true, data: item });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// PUT /api/items/:id - 更新商品信息
router.put('/:id', upload.single('image'), async (req, res) => {
  try {
    const db = req.db;
    const item = await db.prepare(`SELECT * FROM items WHERE id = ?`).get(req.params.id);
    if (!item) return res.status(404).json({ success: false, message: '商品不存在' });

    const { name, barcode, category_id, unit, min_stock, notes } = req.body;
    let image_path = item.image_path;

    if (req.file) {
      // 删除旧图片
      if (item.image_path) {
        const oldPath = path.join(__dirname, '..', item.image_path);
        if (fs.existsSync(oldPath)) fs.unlinkSync(oldPath);
      }
      image_path = `/uploads/${req.file.filename}`;
    }

    await db.prepare(`
      UPDATE items SET
        name = ?, barcode = ?, category_id = ?, image_path = ?,
        unit = ?, min_stock = ?, notes = ?,
        updated_at = datetime('now', 'localtime')
      WHERE id = ?
    `).run(
      name ?? item.name,
      barcode ?? item.barcode,
      category_id ?? item.category_id,
      image_path,
      unit ?? item.unit,
      min_stock ?? item.min_stock,
      notes ?? item.notes,
      req.params.id
    );

    const updated = await db.prepare(`SELECT * FROM items WHERE id = ?`).get(req.params.id);
    res.json({ success: true, data: updated });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// DELETE /api/items/:id - 删除商品
router.delete('/:id', async (req, res) => {
  try {
    const db = req.db;
    const item = await db.prepare(`SELECT * FROM items WHERE id = ?`).get(req.params.id);
    if (!item) return res.status(404).json({ success: false, message: '商品不存在' });
    
    // 删除图片
    if (item.image_path) {
      const imgPath = path.join(__dirname, '..', item.image_path);
      if (fs.existsSync(imgPath)) fs.unlinkSync(imgPath);
    }
    
    // 级联删除关联的库存记录和消耗日志
    await db.prepare(`DELETE FROM inventory WHERE item_id = ?`).run(req.params.id);
    await db.prepare(`DELETE FROM consumption_log WHERE item_id = ?`).run(req.params.id);
    
    await db.prepare(`DELETE FROM items WHERE id = ?`).run(req.params.id);
    res.json({ success: true, message: '删除成功' });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

module.exports = router;
