# -*- coding: utf-8 -*-
"""Employee-facing AI assistant for Ezz Pharmacy."""
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from flask import jsonify, request
from openai import OpenAI
from daily_shortages import ensure_schema as ensure_pharmacy_shortage_schema, list_shortages as list_pharmacy_shortages, stats as pharmacy_shortage_stats, create_shortage as create_pharmacy_shortage, update_shortage as update_pharmacy_shortage, set_available as set_pharmacy_shortage_available, undo_last as undo_pharmacy_shortage

_LOCK = threading.Lock()
_BUCKETS = defaultdict(deque)
_WINDOW = 3600
_MAX_PER_USER = 60


def _clean(v):
    return str(v or "").strip()


def _compact_item(i):
    return {
        "رقم_الصنف": i.get("Item_ID"),
        "المنتج": i.get("Product_Name"),
        "الكمية": i.get("Quantity"),
        "التوفر": i.get("Availability_Status"),
        "السعر": i.get("Available_Price"),
        "بعد_الخصم": i.get("Discounted_Price"),
        "سبب_عدم_التوفر": i.get("Unavailable_Reason"),
        "ملاحظة": i.get("Availability_Note"),
        "تأكيد_السعر": i.get("Price_Confirmation_Required"),
        "الصورة_موجودة": bool(i.get("Image_Path")),
    }


def _compact_order(o):
    return {
        "رقم_الطلب": o.get("Order_ID"),
        "العميل": o.get("Customer_Name"),
        "الجوال": o.get("Phone"),
        "التاريخ": o.get("Order_Date"),
        "الحالة": o.get("Status"),
        "حالة_التواصل": o.get("Contact_Status"),
        "آخر_تواصل": o.get("Last_Contact_Date"),
        "موعد_المتابعة": o.get("Next_Followup_Date"),
        "الملاحظات": o.get("Notes"),
        "المنتجات": [_compact_item(i) for i in (o.get("Items") or [])],
    }


def _check_limit(username):
    now = time.time()
    with _LOCK:
        q = _BUCKETS[username]
        while q and now - q[0] > _WINDOW:
            q.popleft()
        if len(q) >= _MAX_PER_USER:
            return False
        q.append(now)
        return True


def get_order(db, order_id):
    o = db.get_order(_clean(order_id))
    return _compact_order(o) if o else {"error": "الطلب غير موجود"}


def search_orders(db, query="", status="", limit=30):
    q = _clean(query).lower()
    status = _clean(status)
    rows = []
    for o in db.get_all_orders():
        if status and str(o.get("Status") or "") != status:
            continue
        if q:
            blob = " ".join([
                str(o.get("Order_ID") or ""),
                str(o.get("Customer_Name") or ""),
                str(o.get("Phone") or ""),
                str(o.get("Product_Name") or ""),
                str(o.get("Notes") or ""),
                " ".join(str(i.get("Product_Name") or "") for i in (o.get("Items") or [])),
            ]).lower()
            terms = [x for x in re.split(r"\s+", q) if x]
            if not any(t in blob for t in terms):
                continue
        rows.append(o)
    rows.sort(key=lambda x: str(x.get("Created_At") or ""), reverse=True)
    return {"عدد_النتائج": len(rows), "الطلبات": [_compact_order(o) for o in rows[:max(1, min(int(limit or 30), 100))]]}


def customer_history(db, customer_name="", phone="", limit=50):
    name = _clean(customer_name).lower()
    phone = re.sub(r"\D", "", _clean(phone))
    if not name and not phone:
        return {"error": "أرسل اسم العميل أو الجوال"}
    rows = []
    for o in db.get_all_orders():
        oname = str(o.get("Customer_Name") or "").lower()
        ophone = re.sub(r"\D", "", str(o.get("Phone") or ""))
        if name and name not in oname:
            continue
        if phone and phone not in ophone and ophone not in phone:
            continue
        rows.append(o)
    rows.sort(key=lambda x: str(x.get("Created_At") or ""), reverse=True)
    return {"عدد_الطلبات": len(rows), "الطلبات": [_compact_order(o) for o in rows[:max(1, min(int(limit or 50), 100))]]}


def shortages(db, limit=100):
    out = []
    for o in db.get_all_orders():
        pending = [i for i in (o.get("Items") or []) if i.get("Availability_Status") == "بانتظار التوفر"]
        if pending:
            out.append({
                "رقم_الطلب": o.get("Order_ID"),
                "العميل": o.get("Customer_Name"),
                "الجوال": o.get("Phone"),
                "الملاحظات": o.get("Notes"),
                "النواقص": [_compact_item(i) for i in pending],
            })
    return {"عدد_طلبات_النواقص": len(out), "النواقص": out[:max(1, min(int(limit or 100), 200))]}


def pharmacy_shortages():
    ensure_pharmacy_shortage_schema()
    rows = list_pharmacy_shortages()
    stats = pharmacy_shortage_stats()
    pending = [r for r in rows if r.get("status") == "pending"]
    available = [r for r in rows if r.get("status") == "available"]
    return {
        "المصدر": "نواقص الصيدلية",
        "إجمالي_السجلات": int(stats.get("total", 0)),
        "بانتظار_التوفير": int(stats.get("pending", 0)),
        "تم_التوفير": int(stats.get("available", 0)),
        "الأصناف_الناقصة_حاليًا": [
            {
                "رقم_النقص": r.get("shortage_id"),
                "المنتج": r.get("product_name"),
                "الكمية": r.get("quantity"),
                "الملاحظة": r.get("note"),
                "أضيف_بواسطة": r.get("created_by"),
                "تاريخ_الإضافة": r.get("created_at")
            }
            for r in pending
        ],
        "آخر_الأصناف_التي_تم_توفيرها": [
            {
                "رقم_النقص": r.get("shortage_id"),
                "المنتج": r.get("product_name"),
                "الكمية": r.get("quantity"),
                "تاريخ_التوفير": r.get("resolved_at")
            }
            for r in available[:30]
        ]
    }


MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_memories (
    memory_id TEXT PRIMARY KEY,
    memory_text TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'rule',
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_ai_memories_active ON ai_memories(active, created_at DESC);
"""


def _ensure_memory_schema(db):
    with db._connect() as conn:
        conn.execute(MEMORY_SCHEMA)


def _memory_rows(db, query="", limit=20):
    _ensure_memory_schema(db)
    q = _clean(query).lower()
    with db._connect() as conn:
        rows = conn.execute(
            "SELECT memory_id,memory_text,memory_type,created_by,created_at "
            "FROM ai_memories WHERE active=TRUE ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    rows = [dict(r) for r in rows]
    if not q:
        return rows[:limit]
    terms = [x for x in re.split(r"\s+", q) if len(x) >= 2]
    ranked = []
    for r in rows:
        score = sum(1 for t in terms if t in r["memory_text"].lower())
        if score:
            ranked.append((score, r))
    ranked.sort(key=lambda x: (-x[0], x[1]["created_at"]))
    return [r for _, r in ranked[:limit]]


def _save_memory(db, text, user_name):
    text = _clean(text)
    if not text:
        return {"saved": False}
    _ensure_memory_schema(db)
    import uuid
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M:%S")
    with db._connect() as conn:
        existing = conn.execute(
            "SELECT memory_id FROM ai_memories WHERE active=TRUE AND lower(memory_text)=lower(%s) LIMIT 1",
            (text,)
        ).fetchone()
        if existing:
            return {"saved": False, "existing": True}
        mid = "AIM-" + uuid.uuid4().hex[:12].upper()
        conn.execute(
            "INSERT INTO ai_memories(memory_id,memory_text,memory_type,created_by,created_at,active) VALUES(%s,%s,%s,%s,%s,TRUE)",
            (mid, text, "rule", user_name, now)
        )
    return {"saved": True}


def _learning_request(message):
    text = _clean(message)
    prefixes = (
        "احفظ عندك ",
        "احفظ ",
        "تذكر أن ",
        "تذكر ان ",
        "من الآن ",
        "من الان ",
        "اعتبر أن ",
        "اعتبر ان ",
        "قاعدة: ",
        "معلومة: ",
    )
    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].strip()
    return None


def dashboard_stats(db):
    from db import STATUS_PENDING, STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE, STATUS_CONTACTED, STATUS_NOT_PICKED, STATUS_PICKED_UP, CONTACT_AWAITING
    from datetime import datetime
    from zoneinfo import ZoneInfo
    orders = db.get_all_orders()
    today = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d")
    c = lambda fn: sum(1 for o in orders if fn(o))
    return {
        "التاريخ": today,
        "إجمالي_الطلبات": len(orders),
        "قيد_الانتظار": c(lambda o: o.get("Status") == STATUS_PENDING),
        "جاهز_للتواصل": c(lambda o: o.get("Status") in (STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE) and o.get("Contact_Status") in ("", "لم يتم التواصل")),
        "بانتظار_رد_العميل": c(lambda o: o.get("Contact_Status") == CONTACT_AWAITING),
        "قيد_المتابعة": c(lambda o: o.get("Status") in (STATUS_CONTACTED, STATUS_NOT_PICKED)),
        "مستلمة": c(lambda o: o.get("Status") == STATUS_PICKED_UP),
        "نواقص": sum(1 for o in orders if any(i.get("Availability_Status") == "بانتظار التوفر" for i in (o.get("Items") or []))),
    }



_PENDING_ACTIONS = {}
_PENDING_LOCK = threading.Lock()
_PENDING_TTL = 300

def _new_pending(user_id, action, args, label):
    import uuid
    token = uuid.uuid4().hex
    now = time.time()
    with _PENDING_LOCK:
        _PENDING_ACTIONS[token] = {
            "user_id": str(user_id),
            "action": action,
            "args": args,
            "label": label,
            "created_at": now,
        }
        for k,v in list(_PENDING_ACTIONS.items()):
            if now - v["created_at"] > _PENDING_TTL:
                _PENDING_ACTIONS.pop(k, None)
    return token

def _take_pending(token, user_id):
    with _PENDING_LOCK:
        row = _PENDING_ACTIONS.get(str(token))
        if not row:
            return None
        if row["user_id"] != str(user_id) or time.time() - row["created_at"] > _PENDING_TTL:
            _PENDING_ACTIONS.pop(str(token), None)
            return None
        _PENDING_ACTIONS.pop(str(token), None)
        return row

def _action_label(name, args, db):
    labels = {
        "set_item_availability": "تغيير حالة توفر منتج داخل طلب",
        "undo_order": "التراجع عن آخر عملية في الطلب",
        "contact_order": "تسجيل التواصل مع العميل",
        "set_contact_status": "تغيير حالة التواصل مع العميل",
        "pickup_order": "تسجيل استلام العميل للطلب",
        "postpone_order": "تأجيل متابعة الطلب",
        "cancel_order": "إلغاء الطلب",
        "delete_order": "حذف الطلب نهائيًا",
        "create_order": "إنشاء طلب جديد",
        "update_order": "تعديل بيانات الطلب",
        "create_pharmacy_shortage": "إضافة نقص للصيدلية",
        "update_pharmacy_shortage": "تعديل نقص الصيدلية",
        "mark_pharmacy_shortage_available": "تسجيل توفير نقص الصيدلية",
        "undo_pharmacy_shortage": "التراجع عن آخر عملية في نقص الصيدلية",
    }
    title = labels.get(name, name)
    oid = args.get("order_id")
    if oid:
        title += f" — الطلب {oid}"
    sid = args.get("shortage_id")
    if sid:
        title += f" — النقص {sid}"
    return title

MUTATING_TOOLS = {
    "set_item_availability",
    "undo_order",
    "contact_order",
    "set_contact_status",
    "pickup_order",
    "postpone_order",
    "cancel_order",
    "delete_order",
    "create_order",
    "update_order",
    "create_pharmacy_shortage",
    "update_pharmacy_shortage",
    "mark_pharmacy_shortage_available",
    "undo_pharmacy_shortage",
}

TOOLS = [
    {"type":"function","name":"get_order","description":"اقرأ طلبًا محددًا من النظام باستخدام رقم الطلب.","parameters":{"type":"object","properties":{"order_id":{"type":"string"}},"required":["order_id"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"search_orders","description":"ابحث عن الطلبات بالاسم أو الجوال أو المنتج أو رقم الطلب، ويمكنك فلترة الحالة.","parameters":{"type":"object","properties":{"query":{"type":"string"},"status":{"type":"string"},"limit":{"type":"integer"}},"required":["query","status","limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"customer_history","description":"اعرض تاريخ طلبات عميل بالاسم أو الجوال.","parameters":{"type":"object","properties":{"customer_name":{"type":"string"},"phone":{"type":"string"},"limit":{"type":"integer"}},"required":["customer_name","phone","limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_customer_shortages","description":"اعرض نواقص العملاء الحالية: الطلبات التي فيها منتجات بانتظار التوفر، مع رقم الطلب والعميل والمنتجات.","parameters":{"type":"object","properties":{"limit":{"type":"integer"}},"required":["limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_pharmacy_shortages","description":"اعرض نواقص الصيدلية المسجلة في صفحة النواقص اليومية. استخدم هذه الأداة عندما يقول المستخدم نواقص الصيدلية أو شنو ناقص علينا أو نواقص المخزن/الصيدلية.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_dashboard_stats","description":"اعرض إحصائيات النظام الحالية.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False},"strict":True},
    {"type":"function","name":"set_item_availability","description":"تغيير حالة توفر منتج داخل طلب. هذا إجراء تشغيلي وسيطلب النظام تأكيد الموظف قبل التنفيذ.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"item_id":{"type":"string"},"availability_status":{"type":"string","enum":["متوفر","غير متوفر","بانتظار التوفر"]},"available_price":{"type":"string"},"discounted_price":{"type":"string"},"unavailable_reason":{"type":"string"},"availability_note":{"type":"string"},"price_confirmation_required":{"type":"boolean"}},"required":["order_id","item_id","availability_status","available_price","discounted_price","unavailable_reason","availability_note","price_confirmation_required"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"undo_order","description":"التراجع عن آخر عملية مسجلة على طلب.","parameters":{"type":"object","properties":{"order_id":{"type":"string"}},"required":["order_id"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"contact_order","description":"تسجيل التواصل مع العميل وتحديد متابعة لاحقة. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"followup_days":{"type":"integer"}},"required":["order_id","followup_days"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"set_contact_status","description":"تغيير حالة التواصل مع العميل وإضافة ملاحظة. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"contact_status":{"type":"string"},"note":{"type":"string"}}, "required":["order_id","contact_status","note"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"pickup_order","description":"تسجيل استلام العميل للطلب. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"force":{"type":"boolean"}},"required":["order_id","force"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"postpone_order","description":"تأجيل متابعة الطلب. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"days":{"type":"integer"},"custom_date":{"type":"string"}},"required":["order_id","days","custom_date"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"cancel_order","description":"إلغاء الطلب مع سبب اختياري. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"note":{"type":"string"}},"required":["order_id","note"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"delete_order","description":"حذف الطلب نهائيًا. يتطلب تأكيدًا صريحًا جدًا من الموظف.","parameters":{"type":"object","properties":{"order_id":{"type":"string"}},"required":["order_id"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"create_order","description":"إنشاء طلب عميل جديد. يتطلب تأكيد الموظف قبل الحفظ.","parameters":{"type":"object","properties":{"customer_name":{"type":"string"},"phone":{"type":"string"},"products":{"type":"array","items":{"type":"object","properties":{"product_name":{"type":"string"},"quantity":{"type":"integer"}},"required":["product_name","quantity"],"additionalProperties":False}},"notes":{"type":"string"},"order_date":{"type":"string"}},"required":["customer_name","phone","products","notes","order_date"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"update_order","description":"تعديل بيانات طلب موجود. يتطلب تأكيد الموظف قبل الحفظ.","parameters":{"type":"object","properties":{"order_id":{"type":"string"},"customer_name":{"type":"string"},"phone":{"type":"string"},"notes":{"type":"string"},"order_date":{"type":"string"}},"required":["order_id","customer_name","phone","notes","order_date"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"create_pharmacy_shortage","description":"إضافة صنف جديد إلى نواقص الصيدلية. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"product_name":{"type":"string"},"quantity":{"type":"integer"},"note":{"type":"string"}},"required":["product_name","quantity","note"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"update_pharmacy_shortage","description":"تعديل نقص موجود في صفحة نواقص الصيدلية. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"shortage_id":{"type":"string"},"product_name":{"type":"string"},"quantity":{"type":"integer"},"note":{"type":"string"}},"required":["shortage_id","product_name","quantity","note"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"mark_pharmacy_shortage_available","description":"تسجيل أن نقص الصيدلية تم توفيره. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"shortage_id":{"type":"string"}},"required":["shortage_id"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"undo_pharmacy_shortage","description":"التراجع عن آخر عملية في نقص الصيدلية. يتطلب تأكيد الموظف.","parameters":{"type":"object","properties":{"shortage_id":{"type":"string"}},"required":["shortage_id"],"additionalProperties":False},"strict":True},
]



def _execute_action(name, args, db, user):
    uname = str((user or {}).get("name") or (user or {}).get("username") or "موظف")
    if name == "set_item_availability":
        order_id, item_id = args["order_id"], args["item_id"]
        updates = [{
            "Item_ID": item_id,
            "availability_status": args["availability_status"],
            "available_price": args["available_price"],
            "discounted_price": args["discounted_price"],
            "unavailable_reason": args["unavailable_reason"],
            "availability_note": args["availability_note"],
            "price_confirmation_required": args["price_confirmation_required"],
        }]
        return db.set_availability(order_id, updates, None, uname)
    if name == "undo_order":
        return db.undo_last(args["order_id"], uname)
    if name == "contact_order":
        return db.mark_contacted(args["order_id"], int(args["followup_days"]), uname)
    if name == "set_contact_status":
        return db.set_contact_status(args["order_id"], args["contact_status"], args["note"], uname)
    if name == "pickup_order":
        return db.mark_pickup(args["order_id"], bool(args["force"]), uname)
    if name == "postpone_order":
        days = args["days"] if int(args["days"] or 0) > 0 else None
        return db.postpone(args["order_id"], days, args["custom_date"] or None, uname)
    if name == "cancel_order":
        return db.cancel_order(args["order_id"], args["note"], uname)
    if name == "delete_order":
        return {"success": bool(db.delete_order(args["order_id"]))}
    if name == "create_order":
        return {"order": db.create_order(args["customer_name"], args["phone"], args["products"], args["notes"], args["order_date"] or None, uname)}
    if name == "update_order":
        fields = {"Customer_Name": args["customer_name"], "Phone": args["phone"], "Notes": args["notes"], "Order_Date": args["order_date"]}
        return {"order": db.update_order(args["order_id"], fields, None, uname)}
    if name == "create_pharmacy_shortage":
        return {"shortage": create_pharmacy_shortage(args["product_name"], args["quantity"], args["note"], uname)}
    if name == "update_pharmacy_shortage":
        return {"shortage": update_pharmacy_shortage(args["shortage_id"], args["product_name"], args["quantity"], args["note"], uname)}
    if name == "mark_pharmacy_shortage_available":
        return {"shortage": set_pharmacy_shortage_available(args["shortage_id"], uname)}
    if name == "undo_pharmacy_shortage":
        return undo_pharmacy_shortage(args["shortage_id"], uname)
    return {"error":"إجراء غير معروف"}


def _tool(name, args, db):
    if name == "get_order":
        return get_order(db, args.get("order_id"))
    if name == "search_orders":
        return search_orders(db, args.get("query"), args.get("status"), args.get("limit"))
    if name == "customer_history":
        return customer_history(db, args.get("customer_name"), args.get("phone"), args.get("limit"))
    if name == "get_customer_shortages":
        return shortages(db, args.get("limit"))
    if name == "get_pharmacy_shortages":
        return pharmacy_shortages()
    if name == "get_dashboard_stats":
        return dashboard_stats(db)
    return {"error":"أداة غير معروفة"}


def install_ai_chat(app, db):
    if getattr(app, "_ezz_ai_employee_installed", False):
        return
    app._ezz_ai_employee_installed = True

    @app.post("/api/ai/execute")
    def ai_execute():
        auth = app.extensions.get("ezz_auth", {})
        getter = auth.get("current_user")
        user = getter() if getter else None
        if not user:
            return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}),401
        body = request.get_json(silent=True) or {}
        token = str(body.get("confirmation_token") or "").strip()
        if not token:
            return jsonify({"error":"رمز التأكيد مفقود"}),400
        pending = _take_pending(token, user.get("user_id"))
        if not pending:
            return jsonify({"error":"انتهت صلاحية التأكيد أو تم استخدامه بالفعل"}),409
        try:
            result = _execute_action(pending["action"], pending["args"], db, user)
            if isinstance(result, dict) and result.get("success") is False:
                return jsonify({"error":"فشلت العملية","result":result}),400
            try:
                audit = app.extensions.get("ezz_auth",{}).get("audit")
                if audit:
                    audit(action="AI Employee Action", note=pending["label"])
            except Exception:
                pass
            return jsonify({"success":True,"action":pending["action"],"label":pending["label"],"result":result,"answer":"تم تنفيذ العملية بنجاح ✅"})
        except Exception as exc:
            app.logger.exception("AI employee action failed")
            return jsonify({"error":"تعذر تنفيذ العملية: "+str(exc)}),500


    @app.post("/api/ai/chat")
    def ai_chat():
        auth = app.extensions.get("ezz_auth", {})
        getter = auth.get("current_user")
        user = getter() if getter else None
        if not user:
            return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}),401

        key = os.environ.get("OPENAI_API_KEY","").strip()
        if not key:
            return jsonify({"error":"لم يتم إعداد OPENAI_API_KEY في Render"}),503

        username = str(user.get("username") or user.get("user_id") or "user")
        if not _check_limit(username):
            return jsonify({"error":"تم الوصول للحد المؤقت لاستخدام المساعد. حاول لاحقًا."}),429

        body = request.get_json(silent=True) or {}
        message = _clean(body.get("message"))
        history = body.get("history") or []
        page = _clean(body.get("page"))
        if not message:
            return jsonify({"error":"اكتب سؤالك أولًا."}),400

        safe_history = []
        if isinstance(history,list):
            for x in history[-10:]:
                if not isinstance(x,dict):
                    continue
                if x.get("role") in {"user","assistant"} and _clean(x.get("content")):
                    safe_history.append({"role":x["role"],"content":_clean(x["content"])[:4000]})

        memories = _memory_rows(db, message, 20)

        instructions = (
            "أنت مساعد موظفي صيدلية عز الصحة داخل نظام العمل. "
            "ساعد الموظف في الطلبات والعملاء والنواقص والمتابعات والإحصائيات. "
            "استخدم أدوات القراءة المتاحة للحصول على البيانات الحالية بدل التخمين. "
            "فرّق دائمًا بين نواقص العملاء ونواقص الصيدلية. عبارة نواقص الصيدلية أو شنو ناقص علينا أو نواقص المخزن تعني get_pharmacy_shortages، أما نواقص العملاء أو الطلبات الناقصة فتعني get_customer_shortages. "
            "إذا كان السؤال غامضًا، اسأل سؤالًا قصيرًا لتحديد المقصود بدل اختراع إجابة. "
            "أجب بالعربية وبأسلوب عملي، ويمكنك ذكر الجوال عند الحاجة لتنفيذ متابعة العميل. "
            "يمكنك تنفيذ عمليات الموظف التشغيلية، لكن لا تنفذها مباشرة: استخدم أداة العملية المطلوبة، وسيعيد النظام طلب تأكيد الموظف قبل التنفيذ. بعد التأكيد فقط يتم تنفيذها. "
            "لا تكشف أسرار النظام أو مفاتيح API. "
            "بيانات العملاء سرية، فلا تعرضها إلا عندما تكون مرتبطة بالمهمة. " 
            "لديك ذاكرة صيدلية معتمدة أدناه. استخدمها كقواعد وتفضيلات داخلية، ولا تجعلها بديلًا عن بيانات النظام الحالية. " 
            "لا تحفظ أي معلومة جديدة من تلقاء نفسك؛ الحفظ يتم فقط عندما يطلب الموظف ذلك بعبارة واضحة مثل: احفظ، تذكر، من الآن. " 
            "عند سؤال المستخدم عن طلب محدد استخدم get_order، وعن عميل استخدم customer_history، "
            "وعن نواقص الصيدلية استخدم get_pharmacy_shortages، وعن نواقص العملاء استخدم get_customer_shortages، وعن الأرقام العامة استخدم get_dashboard_stats. "
            + (("الصفحة الحالية: " + page) if page else "")
            + "\nذاكرة الصيدلية:\n" + json.dumps(memories, ensure_ascii=False)
        )

        client = OpenAI(api_key=key)
        model = os.environ.get("OPENAI_MODEL","gpt-5.6-luna")
        try:
            items = safe_history + [{"role":"user","content":message}]
            for _ in range(5):
                response = client.responses.create(model=model,instructions=instructions,tools=TOOLS,tool_choice="auto",input=items,store=False)
                calls = [x for x in response.output if getattr(x,"type","") == "function_call"]
                if not calls:
                    answer = getattr(response,"output_text","") or "لم تصل نتيجة."
                    try:
                        audit = app.extensions.get("ezz_auth",{}).get("audit")
                        if audit:
                            audit(action="AI Employee Assistant",note="استفسار من مساعد الموظفين")
                    except Exception:
                        pass
                    return jsonify({"success":True,"answer":answer})
                items = list(response.output)
                for call in calls:
                    try:
                        args=json.loads(call.arguments or "{}")
                    except Exception:
                        args={}
                    if call.name in MUTATING_TOOLS:
                        label = _action_label(call.name, args, db)
                        token = _new_pending(user.get("user_id"), call.name, args, label)
                        return jsonify({
                            "success": True,
                            "confirmation_required": True,
                            "confirmation_token": token,
                            "action": call.name,
                            "action_label": label,
                            "action_args": args,
                            "answer": "قبل تنفيذ العملية التالية، يرجى تأكيدها."
                        })
                    result=_tool(call.name,args,db)
                    items.append({"type":"function_call_output","call_id":call.call_id,"output":json.dumps(result,ensure_ascii=False)})

            return jsonify({"error":"تعذر إكمال الإجابة ضمن عدد الخطوات المسموح."}),500
        except Exception as exc:
            app.logger.exception("AI employee assistant failed")
            return jsonify({"error":"تعذر تنفيذ المساعد: "+str(exc)}),500
