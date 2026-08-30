# -*- coding: utf-8 -*-
"""Isolated PostgreSQL data access for Daily Pharmacy Shortages.

This module only creates/uses the new pharmacy shortage tables. Existing
orders, order_items, images, users, logs and undo history are not modified.
"""
import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

TZ = ZoneInfo("Asia/Riyadh")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pharmacy_shortages (
    shortage_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'موظف',
    resolved_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pharmacy_shortages_status ON pharmacy_shortages(status);
CREATE INDEX IF NOT EXISTS idx_pharmacy_shortages_created_at ON pharmacy_shortages(created_at DESC);

CREATE TABLE IF NOT EXISTS pharmacy_shortage_undo (
    undo_id TEXT PRIMARY KEY,
    shortage_id TEXT NOT NULL REFERENCES pharmacy_shortages(shortage_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    undone_at TEXT NOT NULL DEFAULT '',
    user_name TEXT NOT NULL DEFAULT 'موظف'
);
CREATE INDEX IF NOT EXISTS idx_pharmacy_shortage_undo_shortage ON pharmacy_shortage_undo(shortage_id, created_at DESC);
"""

def _now():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

def _user_name(user):
    value = str(user or "").strip()
    return value or "موظف"

def _id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

def _connect():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL غير مضبوط")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)

def ensure_schema():
    with _connect() as conn:
        conn.execute(SCHEMA_SQL)

def _row(row):
    if not row:
        return None
    return {
        "shortage_id": row["shortage_id"], "product_name": row["product_name"],
        "quantity": int(row["quantity"]), "note": row["note"] or "",
        "status": row["status"] or "pending", "created_at": row["created_at"],
        "updated_at": row["updated_at"], "created_by": row["created_by"] or "موظف",
        "resolved_at": row["resolved_at"] or "",
    }

def list_shortages(include_cancelled=False):
    with _connect() as conn:
        sql = "SELECT * FROM pharmacy_shortages"
        params = []
        if not include_cancelled:
            sql += " WHERE status <> %s"; params.append("cancelled")
        sql += " ORDER BY CASE WHEN status='pending' THEN 0 ELSE 1 END, created_at DESC"
        return [_row(r) for r in conn.execute(sql, params).fetchall()]

def get_shortage(shortage_id):
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM pharmacy_shortages WHERE shortage_id=%s", (str(shortage_id),)).fetchone())

def _snapshot(conn, shortage_id):
    return _row(conn.execute("SELECT * FROM pharmacy_shortages WHERE shortage_id=%s", (str(shortage_id),)).fetchone())

def _add_undo(conn, shortage_id, action, snapshot, user):
    conn.execute(
        """INSERT INTO pharmacy_shortage_undo
        (undo_id, shortage_id, action, snapshot_json, created_at, undone_at, user_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (_id("PSU"), str(shortage_id), action, json.dumps(snapshot, ensure_ascii=False), _now(), "", _user_name(user)),
    )

def _invalidate_undo(conn, shortage_id):
    conn.execute(
        "UPDATE pharmacy_shortage_undo SET undone_at=%s WHERE shortage_id=%s AND COALESCE(undone_at,'')=''",
        (_now(), str(shortage_id)),
    )

def _log(conn, shortage_id, action, old_status, new_status, note, user):
    conn.execute(
        """INSERT INTO activity_log
        (log_id, order_id, action, old_status, new_status, note, created_at, user_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (_id("LOG"), f"PHARMACY-SHORTAGE:{shortage_id}", action, old_status or "", new_status or "", note or "", _now(), _user_name(user)),
    )

def create_shortage(product_name, quantity, note="", user="موظف"):
    name = str(product_name or "").strip()
    try: qty = int(quantity)
    except (TypeError, ValueError): qty = 0
    if not name: raise ValueError("اسم المنتج مطلوب")
    if qty <= 0: raise ValueError("الكمية يجب أن تكون رقمًا صحيحًا أكبر من صفر")
    now = _now(); sid = _id("PS")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO pharmacy_shortages
            (shortage_id, product_name, quantity, note, status, created_at, updated_at, created_by, resolved_at)
            VALUES (%s,%s,%s,%s,'pending',%s,%s,%s,'')""",
            (sid, name, qty, str(note or "").strip(), now, now, _user_name(user)),
        )
        _log(conn, sid, "إضافة نقص صيدلية", "", "pending", f"{name} × {qty}", user)
    return get_shortage(sid)

def update_shortage(shortage_id, product_name=None, quantity=None, note=None, user="موظف"):
    sid = str(shortage_id)
    with _connect() as conn:
        current = _snapshot(conn, sid)
        if not current: return None
        name = current["product_name"] if product_name is None else str(product_name).strip()
        qty = current["quantity"] if quantity is None else int(quantity)
        memo = current["note"] if note is None else str(note).strip()
        if not name: raise ValueError("اسم المنتج مطلوب")
        if qty <= 0: raise ValueError("الكمية يجب أن تكون رقمًا صحيحًا أكبر من صفر")
        _invalidate_undo(conn, sid); now = _now()
        conn.execute("UPDATE pharmacy_shortages SET product_name=%s, quantity=%s, note=%s, updated_at=%s WHERE shortage_id=%s", (name, qty, memo, now, sid))
        _add_undo(conn, sid, "تعديل نقص صيدلية", current, user)
        _log(conn, sid, "تعديل نقص صيدلية", current["status"], current["status"], f"{name} × {qty}", user)
    return get_shortage(sid)

def set_available(shortage_id, user="موظف"):
    sid = str(shortage_id)
    with _connect() as conn:
        current = _snapshot(conn, sid)
        if not current: return None
        if current["status"] == "available": return current
        _invalidate_undo(conn, sid); now = _now()
        conn.execute("UPDATE pharmacy_shortages SET status='available', resolved_at=%s, updated_at=%s WHERE shortage_id=%s", (now, now, sid))
        _add_undo(conn, sid, "تم توفير المنتج", current, user)
        _log(conn, sid, "تم توفير المنتج", current["status"], "available", "تم توفير نقص الصيدلية", user)
    return get_shortage(sid)

def undo_last(shortage_id, user="موظف"):
    sid = str(shortage_id)
    with _connect() as conn:
        row = conn.execute(
            """SELECT * FROM pharmacy_shortage_undo WHERE shortage_id=%s
            AND COALESCE(undone_at,'')='' ORDER BY created_at DESC LIMIT 1""", (sid,)
        ).fetchone()
        current = _snapshot(conn, sid)
        if not row: return {"error":"لا يوجد إجراء يمكن التراجع عنه لهذا النقص", "code":409}
        if not current: return {"error":"النقص غير موجود", "code":404}
        snapshot = json.loads(row["snapshot_json"]); now = _now()
        conn.execute(
            """UPDATE pharmacy_shortages SET product_name=%s, quantity=%s, note=%s, status=%s,
            created_at=%s, updated_at=%s, created_by=%s, resolved_at=%s WHERE shortage_id=%s""",
            (snapshot["product_name"], int(snapshot["quantity"]), snapshot.get("note", ""), snapshot["status"], snapshot["created_at"], now, snapshot.get("created_by", "موظف"), snapshot.get("resolved_at", ""), sid),
        )
        conn.execute("UPDATE pharmacy_shortage_undo SET undone_at=%s WHERE undo_id=%s", (now, row["undo_id"]))
        _log(conn, sid, f"تراجع عن: {row['action']}", current["status"], snapshot["status"], "تم التراجع عن آخر تغيير", user)
    return {"shortage": get_shortage(sid), "undone_action": row["action"]}

def stats():
    with _connect() as conn:
        row = conn.execute("""SELECT COUNT(*) FILTER (WHERE status='pending') AS pending,
        COUNT(*) FILTER (WHERE status='available') AS available,
        COUNT(*) FILTER (WHERE status='cancelled') AS cancelled, COUNT(*) AS total
        FROM pharmacy_shortages""").fetchone()
    return {k:int(row[k] or 0) for k in ("total","pending","available","cancelled")}
