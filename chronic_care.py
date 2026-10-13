# -*- coding: utf-8 -*-
"""Isolated chronic-treatment follow-up feature backed by PostgreSQL."""

from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import psycopg
from flask import jsonify, redirect, render_template, request, session, url_for
from psycopg.rows import dict_row


TZ = ZoneInfo("Asia/Riyadh")
CUSTOMER_STATUSES = {"active", "postponed", "stopped", "needs_review"}
MEDICATION_STATUSES = {"active", "postponed", "stopped", "needs_review"}
WINDOWS = {"today", "7", "14", "30", "overdue"}
DEFAULT_MESSAGE_TEMPLATES = {
    "general": "السلام عليكم {اسم_العميل}، معك صيدلية عز الصحة. هذه رسالة متابعة للعلاج المزمن، ويسعدنا خدمتك ومتابعة مواعيد إعادة صرف أدويتك.",
    "refill": "السلام عليكم {اسم_العميل}، نذكّرك من صيدلية عز الصحة بأن موعد إعادة صرف {اسم_الدواء} {التركيز} متوقع بتاريخ {موعد_إعادة_الصرف}. للتأكيد أو الاستفسار يسعدنا تواصلك معنا.",
}
_schema_lock = threading.Lock()
_schema_ready = False


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chronic_customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    phone_normalized TEXT NOT NULL UNIQUE,
    followup_status TEXT NOT NULL DEFAULT 'active'
        CHECK (followup_status IN ('active','postponed','stopped','needs_review')),
    reminder_consent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS chronic_medications (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES chronic_customers(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    strength TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','postponed','stopped','needs_review')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS chronic_dispenses (
    id TEXT PRIMARY KEY,
    medication_id TEXT NOT NULL REFERENCES chronic_medications(id) ON DELETE RESTRICT,
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    days_supply INTEGER NOT NULL CHECK (days_supply > 0),
    dispensed_at TIMESTAMPTZ NOT NULL,
    expected_refill_at TIMESTAMPTZ NOT NULL,
    reminder_at TIMESTAMPTZ NOT NULL,
    created_by_user_id TEXT NOT NULL DEFAULT '',
    created_by_name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS chronic_message_templates (
    template_key TEXT PRIMARY KEY CHECK (template_key IN ('general','refill')),
    template_text TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

INSERT INTO chronic_message_templates(template_key, template_text, updated_at) VALUES
    ('general', 'السلام عليكم {اسم_العميل}، معك صيدلية عز الصحة. هذه رسالة متابعة للعلاج المزمن، ويسعدنا خدمتك ومتابعة مواعيد إعادة صرف أدويتك.', CURRENT_TIMESTAMP),
    ('refill', 'السلام عليكم {اسم_العميل}، نذكّرك من صيدلية عز الصحة بأن موعد إعادة صرف {اسم_الدواء} {التركيز} متوقع بتاريخ {موعد_إعادة_الصرف}. للتأكيد أو الاستفسار يسعدنا تواصلك معنا.', CURRENT_TIMESTAMP)
ON CONFLICT (template_key) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_chronic_customers_name ON chronic_customers (lower(name));
CREATE INDEX IF NOT EXISTS idx_chronic_customers_status ON chronic_customers (followup_status);
CREATE INDEX IF NOT EXISTS idx_chronic_medications_customer ON chronic_medications (customer_id);
CREATE INDEX IF NOT EXISTS idx_chronic_medications_name ON chronic_medications (lower(name));
CREATE INDEX IF NOT EXISTS idx_chronic_medications_status ON chronic_medications (status);
CREATE INDEX IF NOT EXISTS idx_chronic_dispenses_medication_date
    ON chronic_dispenses (medication_id, dispensed_at DESC);
CREATE INDEX IF NOT EXISTS idx_chronic_dispenses_expected_refill
    ON chronic_dispenses (expected_refill_at);

ALTER TABLE chronic_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE chronic_medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE chronic_dispenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE chronic_message_templates ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE chronic_customers, chronic_medications, chronic_dispenses, chronic_message_templates FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE chronic_customers, chronic_medications, chronic_dispenses, chronic_message_templates FROM authenticated;
    END IF;
END $$;
"""


LATEST_MEDICATIONS_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (medication_id)
        id, medication_id, quantity, days_supply, dispensed_at,
        expected_refill_at, reminder_at, created_at
    FROM chronic_dispenses
    ORDER BY medication_id, dispensed_at DESC, created_at DESC
)
SELECT
    m.id, m.customer_id, m.name, m.strength, m.status,
    m.created_at, m.updated_at,
    c.name AS customer_name, c.phone, c.followup_status,
    c.reminder_consent,
    l.id AS latest_dispense_id, l.quantity, l.days_supply,
    l.dispensed_at, l.expected_refill_at, l.reminder_at
FROM chronic_medications m
JOIN chronic_customers c ON c.id = m.customer_id
LEFT JOIN latest l ON l.medication_id = m.id
"""


def _db_url():
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL غير مضبوط")
    return value


def _connect():
    return psycopg.connect(_db_url(), row_factory=dict_row, connect_timeout=10)


def ensure_schema(force=False):
    global _schema_ready
    if _schema_ready and not force:
        return
    with _schema_lock:
        if _schema_ready and not force:
            return
        with _connect() as conn:
            conn.execute(SCHEMA_SQL)
        _schema_ready = True


def _now():
    return datetime.now(TZ)


def _id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _normalize_phone(value):
    raw = str(value or "").translate(str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"
    ))
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("966"):
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return "966" + digits[1:]
    if digits.startswith("5") and len(digits) == 9:
        return "966" + digits
    return digits


def _parse_datetime(value, field_name):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} مطلوب")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} غير صحيح") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def _decimal(value, field_name):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} غير صحيح") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} يجب أن تكون أكبر من صفر")
    return parsed


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} غير صحيح") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} يجب أن يكون أكبر من صفر")
    return parsed


def calculate_schedule(dispensed_at, days_supply):
    """Return the refill and reminder timestamps for one dispense."""
    expected = dispensed_at + timedelta(days=days_supply)
    return expected, expected - timedelta(days=3)


def _iso(value):
    if isinstance(value, datetime):
        return value.astimezone(TZ).isoformat(timespec="minutes")
    return value


def _number(value):
    if value is None:
        return None
    value = Decimal(value)
    return int(value) if value == value.to_integral() else float(value)


def _serialize_medication(row):
    item = dict(row)
    for key in ("created_at", "updated_at", "dispensed_at", "expected_refill_at", "reminder_at"):
        item[key] = _iso(item.get(key))
    item["quantity"] = _number(item.get("quantity"))
    return item


def _current_user(app):
    auth = app.extensions.get("ezz_auth") or {}
    provider = auth.get("current_user")
    if callable(provider):
        user = provider()
        if user:
            return user
    if session.get("authenticated") or session.get("user_id"):
        return {
            "id": str(session.get("user_id") or ""),
            "name": str(session.get("name") or session.get("username") or "موظف"),
        }
    return None


def _audit(app, action, note):
    audit = (app.extensions.get("ezz_auth") or {}).get("audit")
    if callable(audit):
        audit(action=action, note=note)


def _api_guard(app):
    if not _current_user(app):
        return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
    return None


def _window_clause(window, params):
    if not window:
        return ""
    if window not in WINDOWS:
        raise ValueError("فلتر المدة غير صحيح")
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "overdue":
        params.extend([now])
        return " AND l.expected_refill_at < %s"
    if window == "today":
        params.extend([today_start, today_start + timedelta(days=1)])
        return " AND l.expected_refill_at >= %s AND l.expected_refill_at < %s"
    end = today_start + timedelta(days=int(window) + 1)
    params.extend([today_start, end])
    return " AND l.expected_refill_at >= %s AND l.expected_refill_at < %s"


def list_medications(search="", status="", window=""):
    params = []
    query = LATEST_MEDICATIONS_SQL + " WHERE 1=1"
    search = str(search or "").strip()
    if search:
        normalized = _normalize_phone(search)
        params.extend([f"%{search}%", f"%{search}%"])
        query += " AND (c.name ILIKE %s OR m.name ILIKE %s"
        if normalized:
            params.append(f"%{normalized}%")
            query += " OR c.phone_normalized LIKE %s"
        query += ")"
    if status:
        if status not in MEDICATION_STATUSES:
            raise ValueError("الحالة غير صحيحة")
        params.append(status)
        query += " AND m.status = %s"
    query += _window_clause(window, params)
    query += " ORDER BY l.expected_refill_at NULLS LAST, c.name, m.name"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_serialize_medication(row) for row in rows]


def list_customers(search=""):
    params = []
    where = ""
    search = str(search or "").strip()
    if search:
        normalized = _normalize_phone(search)
        where = "WHERE (c.name ILIKE %s OR EXISTS (SELECT 1 FROM chronic_medications sm WHERE sm.customer_id=c.id AND sm.name ILIKE %s)"
        params = [f"%{search}%", f"%{search}%"]
        if normalized:
            where += " OR c.phone_normalized LIKE %s"
            params.append(f"%{normalized}%")
        where += ")"
    query = f"""
        SELECT c.*, COUNT(m.id)::INTEGER AS medication_count
        FROM chronic_customers c
        LEFT JOIN chronic_medications m ON m.customer_id=c.id
        {where}
        GROUP BY c.id
        ORDER BY c.updated_at DESC, c.name
    """
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["created_at"] = _iso(item["created_at"])
        item["updated_at"] = _iso(item["updated_at"])
        result.append(item)
    return result


def create_customer(payload):
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    normalized = _normalize_phone(phone)
    status = str(payload.get("followup_status") or "active")
    if not name:
        raise ValueError("اسم العميل مطلوب")
    if len(normalized) < 9:
        raise ValueError("رقم الهاتف غير صحيح")
    if status not in CUSTOMER_STATUSES:
        raise ValueError("حالة المتابعة غير صحيحة")
    now = _now()
    item = {
        "id": _id("CC"), "name": name, "phone": phone,
        "phone_normalized": normalized, "followup_status": status,
        "reminder_consent": bool(payload.get("reminder_consent")),
        "created_at": now, "updated_at": now,
    }
    try:
        with _connect() as conn:
            row = conn.execute("""
                INSERT INTO chronic_customers
                    (id,name,phone,phone_normalized,followup_status,reminder_consent,created_at,updated_at)
                VALUES (%(id)s,%(name)s,%(phone)s,%(phone_normalized)s,%(followup_status)s,%(reminder_consent)s,%(created_at)s,%(updated_at)s)
                RETURNING *
            """, item).fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise ValueError("يوجد ملف متابعة مسجل بهذا الرقم") from exc
    result = dict(row)
    result["created_at"] = _iso(result["created_at"])
    result["updated_at"] = _iso(result["updated_at"])
    return result


def update_customer(customer_id, payload):
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    normalized = _normalize_phone(phone)
    status = str(payload.get("followup_status") or "active")
    if not name:
        raise ValueError("اسم العميل مطلوب")
    if len(normalized) < 9:
        raise ValueError("رقم الهاتف غير صحيح")
    if status not in CUSTOMER_STATUSES:
        raise ValueError("حالة المتابعة غير صحيحة")
    try:
        with _connect() as conn:
            row = conn.execute("""
                UPDATE chronic_customers
                SET name=%s, phone=%s, phone_normalized=%s, followup_status=%s,
                    reminder_consent=%s, updated_at=%s
                WHERE id=%s RETURNING *
            """, (name, phone, normalized, status, bool(payload.get("reminder_consent")), _now(), customer_id)).fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise ValueError("يوجد ملف متابعة مسجل بهذا الرقم") from exc
    if not row:
        return None
    result = dict(row)
    result["created_at"] = _iso(result["created_at"])
    result["updated_at"] = _iso(result["updated_at"])
    return result


def create_medication(customer_id, payload):
    name = str(payload.get("name") or "").strip()
    strength = str(payload.get("strength") or "").strip()
    status = str(payload.get("status") or "active")
    if not name:
        raise ValueError("اسم الدواء مطلوب")
    if status not in MEDICATION_STATUSES:
        raise ValueError("حالة الدواء غير صحيحة")
    now = _now()
    item = {"id": _id("CM"), "customer_id": customer_id, "name": name, "strength": strength, "status": status, "created_at": now, "updated_at": now}
    with _connect() as conn:
        if not conn.execute("SELECT 1 FROM chronic_customers WHERE id=%s", (customer_id,)).fetchone():
            return None
        row = conn.execute("""
            INSERT INTO chronic_medications(id,customer_id,name,strength,status,created_at,updated_at)
            VALUES (%(id)s,%(customer_id)s,%(name)s,%(strength)s,%(status)s,%(created_at)s,%(updated_at)s)
            RETURNING *
        """, item).fetchone()
    result = dict(row)
    result["created_at"] = _iso(result["created_at"])
    result["updated_at"] = _iso(result["updated_at"])
    return result


def update_medication(medication_id, payload):
    name = str(payload.get("name") or "").strip()
    strength = str(payload.get("strength") or "").strip()
    status = str(payload.get("status") or "active")
    if not name:
        raise ValueError("اسم الدواء مطلوب")
    if status not in MEDICATION_STATUSES:
        raise ValueError("حالة الدواء غير صحيحة")
    with _connect() as conn:
        row = conn.execute("""
            UPDATE chronic_medications SET name=%s,strength=%s,status=%s,updated_at=%s
            WHERE id=%s RETURNING *
        """, (name, strength, status, _now(), medication_id)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["created_at"] = _iso(result["created_at"])
    result["updated_at"] = _iso(result["updated_at"])
    return result


def create_dispense(medication_id, payload, actor):
    quantity = _decimal(payload.get("quantity"), "الكمية المصروفة")
    days_supply = _positive_int(payload.get("days_supply"), "عدد الأيام")
    dispensed_at = _parse_datetime(payload.get("dispensed_at"), "تاريخ ووقت الصرف")
    expected, reminder = calculate_schedule(dispensed_at, days_supply)
    now = _now()
    item = {
        "id": _id("CD"), "medication_id": medication_id,
        "quantity": quantity, "days_supply": days_supply,
        "dispensed_at": dispensed_at, "expected_refill_at": expected,
        "reminder_at": reminder,
        "created_by_user_id": str((actor or {}).get("id") or ""),
        "created_by_name": str((actor or {}).get("name") or (actor or {}).get("username") or "موظف"),
        "created_at": now,
    }
    with _connect() as conn:
        if not conn.execute("SELECT 1 FROM chronic_medications WHERE id=%s", (medication_id,)).fetchone():
            return None
        row = conn.execute("""
            INSERT INTO chronic_dispenses
                (id,medication_id,quantity,days_supply,dispensed_at,expected_refill_at,
                 reminder_at,created_by_user_id,created_by_name,created_at)
            VALUES (%(id)s,%(medication_id)s,%(quantity)s,%(days_supply)s,%(dispensed_at)s,
                    %(expected_refill_at)s,%(reminder_at)s,%(created_by_user_id)s,
                    %(created_by_name)s,%(created_at)s)
            RETURNING *
        """, item).fetchone()
        conn.execute("UPDATE chronic_medications SET updated_at=%s WHERE id=%s", (now, medication_id))
    result = dict(row)
    for key in ("dispensed_at", "expected_refill_at", "reminder_at", "created_at"):
        result[key] = _iso(result[key])
    result["quantity"] = _number(result["quantity"])
    return result


def dispense_history(medication_id):
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM chronic_dispenses WHERE medication_id=%s
            ORDER BY dispensed_at DESC, created_at DESC
        """, (medication_id,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("dispensed_at", "expected_refill_at", "reminder_at", "created_at"):
            item[key] = _iso(item[key])
        item["quantity"] = _number(item["quantity"])
        result.append(item)
    return result


def dashboard_summary():
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with _connect() as conn:
        row = conn.execute("""
            WITH latest AS (
                SELECT DISTINCT ON (medication_id) medication_id, expected_refill_at
                FROM chronic_dispenses
                ORDER BY medication_id, dispensed_at DESC, created_at DESC
            )
            SELECT
                (SELECT COUNT(*) FROM chronic_customers WHERE followup_status='active')::INTEGER AS active_customers,
                (SELECT COUNT(*) FROM chronic_medications am JOIN chronic_customers ac ON ac.id=am.customer_id WHERE am.status='active' AND ac.followup_status='active')::INTEGER AS active_medications,
                COUNT(*) FILTER (WHERE l.expected_refill_at >= %s AND l.expected_refill_at < %s)::INTEGER AS due_today,
                COUNT(*) FILTER (WHERE l.expected_refill_at >= %s AND l.expected_refill_at < %s)::INTEGER AS due_7,
                COUNT(*) FILTER (WHERE l.expected_refill_at >= %s AND l.expected_refill_at < %s)::INTEGER AS due_14,
                COUNT(*) FILTER (WHERE l.expected_refill_at >= %s AND l.expected_refill_at < %s)::INTEGER AS due_30,
                COUNT(*) FILTER (WHERE l.expected_refill_at < %s)::INTEGER AS overdue
            FROM chronic_medications m
            JOIN chronic_customers c ON c.id=m.customer_id
            JOIN latest l ON l.medication_id=m.id
            WHERE m.status IN ('active','needs_review') AND c.followup_status IN ('active','needs_review')
        """, (
            today, today + timedelta(days=1),
            today, today + timedelta(days=8),
            today, today + timedelta(days=15),
            today, today + timedelta(days=31), now,
        )).fetchone()
    return dict(row)


def forecast_report():
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=31)
    query = LATEST_MEDICATIONS_SQL + """
        WHERE m.status IN ('active','needs_review')
          AND c.followup_status IN ('active','needs_review')
          AND l.expected_refill_at >= %s AND l.expected_refill_at < %s
        ORDER BY lower(m.name), m.strength, l.expected_refill_at, c.name
    """
    with _connect() as conn:
        rows = conn.execute(query, (today, end)).fetchall()
    groups = {}
    for raw in rows:
        row = _serialize_medication(raw)
        key = (row["name"].strip().casefold(), row["strength"].strip().casefold())
        group = groups.setdefault(key, {
            "name": row["name"], "strength": row["strength"],
            "days_0_7": 0, "days_8_14": 0, "days_15_30": 0,
            "refill_operations": 0, "expected_quantity": 0,
            "customer_ids": set(), "customers": [],
        })
        expected = datetime.fromisoformat(row["expected_refill_at"])
        delta = (expected.astimezone(TZ).date() - today.date()).days
        if delta <= 7:
            group["days_0_7"] += 1
        elif delta <= 14:
            group["days_8_14"] += 1
        else:
            group["days_15_30"] += 1
        group["refill_operations"] += 1
        group["expected_quantity"] += Decimal(str(row["quantity"] or 0))
        group["customer_ids"].add(row["customer_id"])
        group["customers"].append({
            "customer_id": row["customer_id"], "customer_name": row["customer_name"],
            "phone": row["phone"], "medication_id": row["id"],
            "expected_refill_at": row["expected_refill_at"], "quantity": row["quantity"],
        })
    result = []
    for group in groups.values():
        group["customer_count"] = len(group.pop("customer_ids"))
        group["expected_quantity"] = _number(group["expected_quantity"])
        group["total_30"] = group["refill_operations"]
        result.append(group)
    result.sort(key=lambda item: (item["name"].casefold(), item["strength"].casefold()))
    return result


def get_message_templates():
    result = dict(DEFAULT_MESSAGE_TEMPLATES)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT template_key, template_text FROM chronic_message_templates"
        ).fetchall()
    for row in rows:
        result[row["template_key"]] = row["template_text"]
    return result


def update_message_templates(payload):
    values = {}
    for key in ("general", "refill"):
        text = str(payload.get(key) or "").strip()
        if not text:
            raise ValueError("لا يمكن حفظ قالب فارغ")
        if len(text) > 2000:
            raise ValueError("الحد الأقصى لكل قالب هو 2000 حرف")
        values[key] = text
    with _connect() as conn:
        for key, text in values.items():
            conn.execute(
                """
                INSERT INTO chronic_message_templates(template_key, template_text, updated_at)
                VALUES (%s,%s,%s)
                ON CONFLICT (template_key) DO UPDATE
                SET template_text=EXCLUDED.template_text, updated_at=EXCLUDED.updated_at
                """,
                (key, text, _now()),
            )
    return values


def install_chronic_care(app):
    if app.extensions.get("ezz_chronic_care"):
        return
    app.extensions["ezz_chronic_care"] = True

    # Apply the additive, idempotent schema during a real configured startup.
    # Route-level calls below remain as a retry path after transient DB failures.
    if os.environ.get("DATABASE_URL"):
        try:
            ensure_schema()
        except Exception as exc:
            app.logger.exception("Failed to prepare chronic care schema: %s", exc)

    @app.get("/chronic-care")
    def chronic_care_page():
        if not _current_user(app):
            return redirect(url_for("ezz_login", next=request.path))
        ensure_schema()
        return render_template("chronic_care.html")

    @app.get("/chronic-care/forecasts")
    def chronic_care_forecasts_page():
        if not _current_user(app):
            return redirect(url_for("ezz_login", next=request.path))
        ensure_schema()
        return render_template("chronic_refill_forecasts.html")

    @app.get("/api/chronic-care/dashboard")
    def chronic_dashboard_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        return jsonify(dashboard_summary())

    @app.get("/api/chronic-care/customers")
    def chronic_customers_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        return jsonify({"customers": list_customers(request.args.get("search", ""))})

    @app.post("/api/chronic-care/customers")
    def chronic_create_customer_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            customer = create_customer(request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        _audit(app, "Chronic Customer Created", f"تم إنشاء ملف متابعة للعميل {customer['name']}")
        return jsonify({"customer": customer}), 201

    @app.put("/api/chronic-care/customers/<customer_id>")
    def chronic_update_customer_api(customer_id):
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            customer = update_customer(customer_id, request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not customer:
            return jsonify({"error": "ملف العميل غير موجود"}), 404
        _audit(app, "Chronic Customer Updated", f"تم تحديث ملف متابعة العميل {customer['name']}")
        return jsonify({"customer": customer})

    @app.get("/api/chronic-care/medications")
    def chronic_medications_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            rows = list_medications(
                request.args.get("search", ""), request.args.get("status", ""),
                request.args.get("window", ""),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"medications": rows})

    @app.post("/api/chronic-care/customers/<customer_id>/medications")
    def chronic_create_medication_api(customer_id):
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            medication = create_medication(customer_id, request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not medication:
            return jsonify({"error": "ملف العميل غير موجود"}), 404
        _audit(app, "Chronic Medication Created", f"تمت إضافة الدواء {medication['name']}")
        return jsonify({"medication": medication}), 201

    @app.put("/api/chronic-care/medications/<medication_id>")
    def chronic_update_medication_api(medication_id):
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            medication = update_medication(medication_id, request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not medication:
            return jsonify({"error": "الدواء غير موجود"}), 404
        _audit(app, "Chronic Medication Updated", f"تم تحديث الدواء {medication['name']}")
        return jsonify({"medication": medication})

    @app.post("/api/chronic-care/medications/<medication_id>/dispenses")
    def chronic_create_dispense_api(medication_id):
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            dispense = create_dispense(medication_id, request.get_json(silent=True) or {}, _current_user(app))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not dispense:
            return jsonify({"error": "الدواء غير موجود"}), 404
        _audit(app, "Chronic Medication Dispensed", f"تم تسجيل إعادة صرف للدواء {medication_id}")
        return jsonify({"dispense": dispense}), 201

    @app.get("/api/chronic-care/medications/<medication_id>/dispenses")
    def chronic_dispense_history_api(medication_id):
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        return jsonify({"dispenses": dispense_history(medication_id)})

    @app.get("/api/chronic-care/forecasts")
    def chronic_forecasts_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        return jsonify({"medications": forecast_report()})

    @app.get("/api/chronic-care/message-templates")
    def chronic_message_templates_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        return jsonify({"templates": get_message_templates()})

    @app.put("/api/chronic-care/message-templates")
    def chronic_update_message_templates_api():
        denied = _api_guard(app)
        if denied:
            return denied
        ensure_schema()
        try:
            templates = update_message_templates(request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        _audit(app, "Chronic Message Templates Updated", "تم تحديث قوالب رسائل متابعة العلاج المزمن")
        return jsonify({"templates": templates})



