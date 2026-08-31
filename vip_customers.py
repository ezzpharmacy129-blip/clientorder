# -*- coding: utf-8 -*-
"""VIP customers feature. Uses its own PostgreSQL table only."""
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

TZ = ZoneInfo("Asia/Riyadh")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vip_customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    offer_product TEXT NOT NULL,
    offer_price TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'قيد الانتظار',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vip_customers_status ON vip_customers(status);
CREATE INDEX IF NOT EXISTS idx_vip_customers_created_at ON vip_customers(created_at DESC);
"""

def _db_url():
    return os.environ.get("DATABASE_URL", "").strip()

def _now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

def ensure_schema():
    url = _db_url()
    if not url:
        return
    with psycopg.connect(url) as conn:
        conn.execute(SCHEMA_SQL)

def _row(r):
    if not r:
        return None
    return {
        "id": r["id"], "name": r["name"], "phone": r["phone"],
        "offer_product": r["offer_product"], "offer_price": r["offer_price"],
        "status": r["status"], "created_at": r["created_at"], "updated_at": r["updated_at"],
    }

def list_customers():
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        rows = conn.execute("SELECT * FROM vip_customers ORDER BY CASE WHEN status='قيد الانتظار' THEN 0 ELSE 1 END, created_at DESC").fetchall()
    return [_row(r) for r in rows]

def create_customer(name, phone, offer_product, offer_price):
    name = str(name or "").strip()
    phone = str(phone or "").strip()
    offer_product = str(offer_product or "").strip()
    offer_price = str(offer_price or "").strip()
    if not name:
        raise ValueError("اسم العميل مطلوب")
    if not offer_product:
        raise ValueError("منتج العرض مطلوب")
    if not offer_price:
        raise ValueError("سعر العرض مطلوب")
    now = _now()
    item = {
        "id": f"VIP-{uuid.uuid4().hex[:10].upper()}", "name": name, "phone": phone,
        "offer_product": offer_product, "offer_price": offer_price,
        "status": "قيد الانتظار", "created_at": now, "updated_at": now,
    }
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        conn.execute("INSERT INTO vip_customers(id,name,phone,offer_product,offer_price,status,created_at,updated_at) VALUES (%(id)s,%(name)s,%(phone)s,%(offer_product)s,%(offer_price)s,%(status)s,%(created_at)s,%(updated_at)s)", item)
    return item

def set_status(customer_id, status):
    if status not in {"قيد الانتظار", "تم استلام العرض"}:
        raise ValueError("حالة غير صحيحة")
    now = _now()
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        row = conn.execute("UPDATE vip_customers SET status=%s, updated_at=%s WHERE id=%s RETURNING *", (status, now, customer_id)).fetchone()
    return _row(row)
