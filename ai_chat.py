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
from daily_shortages import ensure_schema as ensure_pharmacy_shortage_schema, list_shortages as list_pharmacy_shortages, stats as pharmacy_shortage_stats

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


TOOLS = [
    {"type":"function","name":"get_order","description":"اقرأ طلبًا محددًا من النظام باستخدام رقم الطلب.","parameters":{"type":"object","properties":{"order_id":{"type":"string"}},"required":["order_id"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"search_orders","description":"ابحث عن الطلبات بالاسم أو الجوال أو المنتج أو رقم الطلب، ويمكنك فلترة الحالة.","parameters":{"type":"object","properties":{"query":{"type":"string"},"status":{"type":"string"},"limit":{"type":"integer"}},"required":["query","status","limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"customer_history","description":"اعرض تاريخ طلبات عميل بالاسم أو الجوال.","parameters":{"type":"object","properties":{"customer_name":{"type":"string"},"phone":{"type":"string"},"limit":{"type":"integer"}},"required":["customer_name","phone","limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_customer_shortages","description":"اعرض نواقص العملاء الحالية: الطلبات التي فيها منتجات بانتظار التوفر، مع رقم الطلب والعميل والمنتجات.","parameters":{"type":"object","properties":{"limit":{"type":"integer"}},"required":["limit"],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_pharmacy_shortages","description":"اعرض نواقص الصيدلية المسجلة في صفحة النواقص اليومية. استخدم هذه الأداة عندما يقول المستخدم نواقص الصيدلية أو شنو ناقص علينا أو نواقص المخزن/الصيدلية.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False},"strict":True},
    {"type":"function","name":"get_dashboard_stats","description":"اعرض إحصائيات النظام الحالية.","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False},"strict":True},
]


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

        instructions = (
            "أنت مساعد موظفي صيدلية عز الصحة داخل نظام العمل. "
            "ساعد الموظف في الطلبات والعملاء والنواقص والمتابعات والإحصائيات. "
            "استخدم أدوات القراءة المتاحة للحصول على البيانات الحالية بدل التخمين. "
            "فرّق دائمًا بين نواقص العملاء ونواقص الصيدلية. عبارة نواقص الصيدلية أو شنو ناقص علينا أو نواقص المخزن تعني get_pharmacy_shortages، أما نواقص العملاء أو الطلبات الناقصة فتعني get_customer_shortages. "
            "إذا كان السؤال غامضًا، اسأل سؤالًا قصيرًا لتحديد المقصود بدل اختراع إجابة. "
            "أجب بالعربية وبأسلوب عملي، ويمكنك ذكر الجوال عند الحاجة لتنفيذ متابعة العميل. "
            "لا تدّعي تنفيذ تعديل أو حذف أو حفظ؛ أدواتك الحالية للقراءة فقط. "
            "لا تكشف أسرار النظام أو مفاتيح API. "
            "بيانات العملاء سرية، فلا تعرضها إلا عندما تكون مرتبطة بالمهمة. "
            "عند سؤال المستخدم عن طلب محدد استخدم get_order، وعن عميل استخدم customer_history، "
            "وعن نواقص الصيدلية استخدم get_pharmacy_shortages، وعن نواقص العملاء استخدم get_customer_shortages، وعن الأرقام العامة استخدم get_dashboard_stats. "
            + (("الصفحة الحالية: " + page) if page else "")
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
                    result=_tool(call.name,args,db)
                    items.append({"type":"function_call_output","call_id":call.call_id,"output":json.dumps(result,ensure_ascii=False)})

            return jsonify({"error":"تعذر إكمال الإجابة ضمن عدد الخطوات المسموح."}),500
        except Exception as exc:
            app.logger.exception("AI employee assistant failed")
            return jsonify({"error":"تعذر تنفيذ المساعد: "+str(exc)}),500
