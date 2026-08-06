#!/usr/bin/env python3
"""
HomeHamster 数据库初始化脚本
用法: python3 init_db.py

功能:
1. 连接 PostgreSQL 服务器
2. 创建 homehamster 数据库（如不存在）
3. 执行 init.sql 建表
4. 验证表结构

使用 pg8000 驱动，兼容服务器 GBK 编码环境。
"""

import os
import sys
from pathlib import Path

import pg8000

# ---- 配置 ----
DB_HOST = os.getenv("DB_HOST", "192.168.3.44")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "19930923")
DB_NAME = os.getenv("DB_NAME", "homehamster")

# init.sql 路径
SQL_FILE = Path(__file__).parent / "sql" / "init.sql"


def decode_gbk(text: str) -> str:
    """尝试将 GBK 编码的字符串解码为可读文本"""
    try:
        return text.encode("latin-1").decode("gbk")
    except Exception:
        return text


def connect(dbname="postgres"):
    """连接到 PostgreSQL（无 SSL）"""
    return pg8000.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=dbname,
        timeout=15,
        ssl_context=None,
    )


def step1_check_server():
    """步骤1: 检查服务器连接"""
    print("=" * 60)
    print("步骤 1/4: 检查 PostgreSQL 服务器连接")
    print("=" * 60)
    try:
        conn = connect("postgres")
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"  ✅ 连接成功")
        print(f"  📋 版本: {version}")

        cur.execute("SHOW server_encoding;")
        print(f"  📋 服务器编码: {cur.fetchone()[0]}")

        cur.execute("SHOW lc_collate;")
        print(f"  📋 排序规则: {cur.fetchone()[0]}")

        # 检查扩展可用性
        cur.execute(
            "SELECT name, installed FROM pg_available_extensions "
            "WHERE name IN ('vector', 'pg_trgm') ORDER BY name;"
        )
        exts = cur.fetchall()
        ext_names = [e[0] for e in exts]
        print(f"  📋 可用扩展: {ext_names}")

        if "vector" not in ext_names:
            print("  ⚠️  警告: pgvector 扩展不可用！Agent 记忆向量功能将无法使用")
            print("     安装方法 (Linux): apt install postgresql-16-pgvector")
            print("     安装方法 (Windows): 从 https://github.com/pgvector/pgvector 下载")
        if "pg_trgm" not in ext_names:
            print("  ⚠️  警告: pg_trgm 扩展不可用！模糊搜索功能将无法使用")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        if isinstance(e, pg8000.InterfaceError) and isinstance(e.args[0], dict):
            msg = decode_gbk(e.args[0].get("M", str(e)))
            print(f"  ❌ 连接失败: {msg}")
        else:
            print(f"  ❌ 连接失败: {e}")
        return False


def step2_create_database():
    """步骤2: 创建数据库"""
    print()
    print("=" * 60)
    print("步骤 2/4: 创建数据库")
    print("=" * 60)
    conn = connect("postgres")
    conn.autocommit = True
    cur = conn.cursor()

    # 检查数据库是否已存在
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
    exists = cur.fetchone()

    if exists:
        print(f"  ℹ️  数据库 '{DB_NAME}' 已存在，跳过创建")
    else:
        cur.execute(f'CREATE DATABASE "{DB_NAME}";')
        print(f"  ✅ 数据库 '{DB_NAME}' 创建成功")

    cur.close()
    conn.close()


def step3_init_tables():
    """步骤3: 执行建表 SQL"""
    print()
    print("=" * 60)
    print("步骤 3/4: 执行建表 SQL")
    print("=" * 60)

    if not SQL_FILE.exists():
        print(f"  ❌ SQL 文件不存在: {SQL_FILE}")
        sys.exit(1)

    sql_content = SQL_FILE.read_text(encoding="utf-8")
    print(f"  📄 SQL 文件: {SQL_FILE}")
    print(f"  📄 文件大小: {len(sql_content)} 字节")

    conn = connect(DB_NAME)
    conn.autocommit = True
    cur = conn.cursor()

    # 逐条执行 SQL（更安全，能跳过已存在对象）
    # 先按分号拆分，过滤掉注释和空语句
    raw_statements = sql_content.split(";")
    success_count = 0
    skip_count = 0
    error_count = 0

    for stmt in raw_statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        # 跳过纯注释
        lines = [l for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
        if not lines:
            continue
        try:
            cur.execute(stmt + ";")
            success_count += 1
        except pg8000.Error as e:
            err_msg = str(e)
            if "already exists" in err_msg.lower():
                skip_count += 1
            else:
                error_count += 1
                # 尝试解码 GBK 错误信息
                if isinstance(e.args[0], dict):
                    decoded = decode_gbk(e.args[0].get("M", ""))
                    print(f"  ⚠️  SQL 错误: {decoded}")
                else:
                    print(f"  ⚠️  SQL 错误: {err_msg}")

    print(f"  ✅ 执行完成: {success_count} 条成功, {skip_count} 条跳过(已存在), {error_count} 条错误")

    cur.close()
    conn.close()


def step4_verify():
    """步骤4: 验证表结构"""
    print()
    print("=" * 60)
    print("步骤 4/4: 验证表结构")
    print("=" * 60)
    conn = connect(DB_NAME)
    conn.autocommit = True
    cur = conn.cursor()

    # 查询所有表
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    print(f"  📋 已创建的表 ({len(tables)} 个):")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        count = cur.fetchone()[0]
        print(f"     • {t}: {count} 行")

    # 验证索引
    cur.execute("""
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)
    indexes = cur.fetchall()
    print(f"\n  📋 已创建的索引 ({len(indexes)} 个):")
    for idx_name, tbl in indexes:
        print(f"     • {tbl}.{idx_name}")

    # 验证触发器
    cur.execute("""
        SELECT trigger_name, event_object_table
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table;
    """)
    triggers = cur.fetchall()
    print(f"\n  📋 已创建的触发器 ({len(triggers)} 个):")
    for trg_name, tbl in triggers:
        print(f"     • {tbl}: {trg_name}")

    # 验证扩展
    cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname;")
    exts = cur.fetchall()
    print(f"\n  📋 已安装的扩展:")
    for name, ver in exts:
        print(f"     • {name} {ver}")

    cur.close()
    conn.close()
    print()
    print("=" * 60)
    print("🎉 数据库初始化完成！")
    print(f"   连接地址: {DB_HOST}:{DB_PORT}")
    print(f"   数据库名: {DB_NAME}")
    print(f"   用户名:   {DB_USER}")
    print("=" * 60)


if __name__ == "__main__":
    print()
    print("🐹 HomeHamster 数据库初始化工具")
    print(f"   服务器: {DB_HOST}:{DB_PORT}")
    print(f"   用户名: {DB_USER}")
    print(f"   数据库: {DB_NAME}")
    print()

    if not step1_check_server():
        print("\n❌ 无法连接到 PostgreSQL 服务器，请检查:")
        print("   1. pg_hba.conf 是否允许 192.168.3.0/24 网段连接")
        print("   2. PostgreSQL 服务是否在运行")
        print("   3. 防火墙是否开放了 5432 端口")
        print("   4. postgresql.conf 中 listen_addresses 是否设为 '*'")
        sys.exit(1)

    step2_create_database()
    step3_init_tables()
    step4_verify()
