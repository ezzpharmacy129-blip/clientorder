# -*- coding: utf-8 -*-
"""Side AI chat that reads Ezz Pharmacy PostgreSQL data automatically."""
import base64
import json
import os
import re
import threading
import time
from collections import defaultdict, deque

from flask import jsonify, request

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_LOCK = threading.Lock()
_BUCKETS = defaultdict(deque)
_WINDOW = 3600
_MAX_PER_USER = 60


def _tokens(text):
    return [x for x in re.split(r"[\s,،.؛;:!?؟/\\()\[\]{}\-]+", str(text or "").lower()) if len(x) >= 2]


def _compact_order(order):
    items = order.get("Items") or []
    return {
        "رقم_الطلب": order.get("Order_ID"),
        "العميل": order.get("Customer_Name"),
        "الجوال": order.get("Phone"),
        "التاريخ": order.get("Order_Date"),
        "الحالة": order.get("Status"),
        "التواصل": order.get("Contact_Status"),
        "موعد_المتابعة": order.get("Next_Followup_Date"),
        "الملاحظات": order.get("Notes"),
        "المنتجات": [
            {
                "item_id": i.get("Item_ID"),
                "المنتج": i.get("Product_Name"),
                "الكمية": i.get("Quantity"),
                "التوفر": i.get("Availability_Status"),
                "السعر": i.get("Available_Price"),
                "بعد_الخصم": i.get("Discounted_Price"),
                "سبب_عدم_التوفر": i.get("Unavailable_Reason"),
                "ملاحظة": i.get("Availability_Note"),
                "صورة_محفوظة": bool(i.get("Image_Path")),
            }
            for i in items
        ],
    }


def _select_data(db, question):
    orders = db.get_all_orders()
    q = str(question or "").lower()
    toks = _tokens(q)

    exact_order_ids = [o for o in orders if str(o.get("Order_ID") or "").lower() in q]
    matches = []
    for o in orders:
        blob = " ".join([
            str(o.get("Order_ID") or ""),
            str(o.get("Customer_Name") or ""),
            str(o.get("Phone") or ""),
            str(o.get("Product_Name") or ""),
            str(o.get("Notes") or ""),
            " ".join(str(i.get("Product_Name") or "") for i in (o.get("Items") or [])),
        ]).lower()
        score = sum(1 for t in toks if t in blob)
        if score:
            matches.append((score, o))
    matches.sort(key=lambda x: (-x[0], str(x[1].get("Created_At") or "")))
    selected = [o for _, o in matches[:80]]
    for o in exact_order_ids:
        if o not in selected:
            selected.insert(0, o)

    # For general questions, provide a bounded recent sample plus exact computed counts.
    selected_ids = {id(o) for o in selected}
    if not selected and orders:
        selected = sorted(orders, key=lambda o: str(o.get("Created_At") or ""), reverse=True)[:60]

    shortages = []
    try:
        for o in orders:
            pending = [i for i in (o.get("Items") or []) if i.get("Availability_Status") == "بانتظار التوفر"]
            if pending:
                shortages.append({
                    "رقم_الطلب": o.get("Order_ID"),
                    "العميل": o.get("Customer_Name"),
                    "الجوال": o.get("Phone"),
                    "المنتجات": [{"المنتج": i.get("Product_Name"), "الكمية": i.get("Quantity")} for i in pending],
                    "الملاحظات": o.get("Notes"),
                })
    except Exception:
        pass

    status_counts = defaultdict(int)
    contact_counts = defaultdict(int)
    product_shortages = defaultdict(int)
    for o in orders:
        status_counts[str(o.get("Status") or "غير محدد")] += 1
        contact_counts[str(o.get("Contact_Status") or "لم يتم التواصل")] += 1
    for s in shortages:
        for i in s["المنتجات"]:
            product_shortages[str(i["المنتج"] or "غير محدد")] += int(i["الكمية"] or 1)

    context = {
        "إجمالي_الطلبات": len(orders),
        "حالات_الطلبات": dict(status_counts),
        "حالات_التواصل": dict(contact_counts),
        "إجمالي_طلبات_النواقص": len(shortages),
        "النواقص_حسب_المنتج": dict(sorted(product_shortages.items(), key=lambda x: -x[1])[:100]),
        "طلبات_مطابقة_للسؤال": [_compact_order(o) for o in selected],
        "آخر_طلبات": [_compact_order(o) for o in (selected if matches else selected[:30])],
        "تنبيه": "هذه البيانات هي لقطة قراءة فقط من قاعدة البيانات. لا تنفذ أي تعديل أو حذف.",
    }
    return context


def _find_image_for_order(db, context, requested_question):
    q = str(requested_question or "").lower()
    wants_image = any(x in q for x in ("صورة", "صور", "image", "photo", "شكل", "كيف شكله"))
    if not wants_image:
        return None
    try:
        candidates = context.get("طلبات_مطابقة_للسؤال") or []
        for o in candidates[:5]:
            for item in o.get("المنتجات", []):
                path = item.get("Image_Path") or item.get("مسار_الصورة")
                if path:
                    raw = db.get_uploaded_image(path)
                    if raw:
                        return raw
    except Exception:
        pass
    return None


def install_ai_chat(app, db):
    if getattr(app, "_ezz_ai_chat_installed", False):
        return
    app._ezz_ai_chat_installed = True

    @app.post("/api/ai/chat")
    def ai_chat():
        auth = app.extensions.get("ezz_auth", {})
        getter = auth.get("current_user")
        user = getter() if getter else None
        if not user:
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        if OpenAI is None:
            return jsonify({"error": "مكتبة OpenAI غير مثبتة"}), 503

        username = str(user.get("username") or user.get("user_id") or "user")
        now = time.time()
        with _LOCK:
            q = _BUCKETS[username]
            while q and now - q[0] > _WINDOW:
                q.popleft()
            if len(q) >= _MAX_PER_USER:
                return jsonify({"error": "تم الوصول للحد المؤقت لاستخدام المساعد. حاول لاحقًا."}), 429
            q.append(now)

        question = str((request.get_json(silent=True) or {}).get("message") or "").strip()
        if not question:
            return jsonify({"error": "اكتب سؤالك أولًا."}), 400

        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            return jsonify({"error": "لم يتم إعداد OPENAI_API_KEY في Render."}), 503

        try:
            context = _select_data(db, question)
            system = (
                "أنت مساعد داخلي لصيدلية عز الصحة. "
                "يمكنك قراءة بيانات النظام التي يرسلها لك الخادم في رسالة المستخدم. "
                "أجب بالعربية وبشكل عملي وواضح. "
                "اعتمد فقط على البيانات المرسلة لك ولا تخمّن الأرقام أو الحالات. "
                "إذا كانت المعلومة غير موجودة قل إنها غير موجودة. "
                "لا تنفذ أي تعديل أو حذف أو تغيير في النظام من خلال هذا الشات. "
                "عند سؤال المستخدم عن الإحصائيات استخدم الأرقام المحسوبة في البيانات. "
                "عند السؤال عن طلب استخدم رقم الطلب واسم العميل والمنتجات والحالة والتواصل. "
                "إذا كانت هناك صور مرتبطة بالطلب وتم تمريرها لك، حللها عند الحاجة."
            )
            payload = {
                "السؤال": question,
                "بيانات_النظام": context,
            }

            content = [
                {"type": "input_text", "text": system + "\n\n" + json.dumps(payload, ensure_ascii=False)}
            ]

            response = OpenAI(api_key=key).responses.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-5.6-luna"),
                input=[{"role": "user", "content": content}],
                store=False,
            )
            answer = getattr(response, "output_text", "") or "لم تُرجع الخدمة نتيجة."

            try:
                audit = app.extensions.get("ezz_auth", {}).get("audit")
                if audit:
                    audit(action="AI Chat", note="استفسار من مساعد النظام")
            except Exception:
                pass

            return jsonify({"success": True, "answer": answer})

        except Exception as exc:
            app.logger.exception("AI chat failed")
            return jsonify({"error": "تعذر تنفيذ استفسار المساعد: " + str(exc)}), 500
