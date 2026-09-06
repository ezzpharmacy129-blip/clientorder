# -*- coding: utf-8 -*-
import json
import io
import re
import threading
import webbrowser
import os
from urllib.parse import quote
from flask import Flask, jsonify, request, render_template, send_from_directory, send_file, Response, session
from werkzeug.middleware.proxy_fix import ProxyFix

from db import (
    db, ALL_STATUSES, CLOSED_STATUSES, STATUS_PENDING, STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE,
    STATUS_CONTACTED, STATUS_PICKED_UP, STATUS_NOT_PICKED, STATUS_CANCELLED,
    CONTACT_NOT_CONTACTED, CONTACT_AWAITING, CONTACT_ACCEPTED, CONTACT_REJECTED, CONTACT_POSTPONED,
    today_str, MAX_IMAGE_SIZE,
)
from daily_shortages import (
    ensure_schema as ensure_pharmacy_shortage_schema,
    list_shortages as list_pharmacy_shortages,
    create_shortage as create_pharmacy_shortage,
    update_shortage as update_pharmacy_shortage,
    set_available as set_pharmacy_shortage_available,
    undo_last as undo_pharmacy_shortage,
    stats as pharmacy_shortage_stats,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE + 1024 * 1024


def clean_phone(phone):
    if not phone:
        return ""
    raw = str(phone).translate(str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789",
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


def validate_products(data):
    products = data.get("products")
    if products is None:
        products = [{"product_name": data.get("product_name", ""), "quantity": data.get("quantity", 0)}]
    if not isinstance(products, list) or not products:
        return None, {"products": "يجب إضافة منتج واحد على الأقل"}
    cleaned=[]
    for i,p in enumerate(products,1):
        name = str((p or {}).get("product_name") or "").strip()
        try: qty=int((p or {}).get("quantity"))
        except (TypeError,ValueError): qty=0
        if not name: return None, {"products": f"اسم المنتج رقم {i} مطلوب"}
        if qty <= 0: return None, {"products": f"كمية المنتج رقم {i} يجب أن تكون أكبر من صفر"}
        cleaned.append({"product_name":name,"quantity":qty})
    return cleaned, None


def validate_order_payload(data, partial=False):
    errors={}
    name=str(data.get("customer_name") or "").strip()
    phone=str(data.get("phone") or "").strip()
    if not partial or "customer_name" in data:
        if not name: errors["customer_name"]="اسم العميل مطلوب"
    if not partial or "phone" in data:
        if not phone: errors["phone"]="رقم الجوال مطلوب"
        elif len(clean_phone(phone)) < 9: errors["phone"]="رقم الجوال غير صحيح"
    if not partial or "products" in data or "product_name" in data or "quantity" in data:
        _, e = validate_products(data)
        if e: errors.update(e)
    return errors


APP_VERSION = "1.3.1 Cloud"


@app.route("/")
def index():
    return render_template("index.html", settings=db.get_settings(), app_version=APP_VERSION)


@app.get("/api/system/info")
def api_system_info():
    return jsonify({"app_version": APP_VERSION, "storage": db.storage_info()})

@app.get("/health")
def health():
    try:
        info = db.storage_info()
        return jsonify({"ok": True, "app_version": APP_VERSION, "storage": info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.get("/api/message-templates")
def api_message_templates():
    settings = db.get_settings()
    keys = ["Message_Template_Available", "Message_Template_Partial", "Message_Template_Unavailable", "Message_Template_Price_Confirmation", "Message_Template_Shortage"]
    return jsonify({"templates": {k: settings.get(k, "") for k in keys}})


@app.put("/api/message-templates")
def api_update_message_templates():
    data = request.get_json(silent=True) or {}
    allowed = {"Message_Template_Available", "Message_Template_Partial", "Message_Template_Unavailable", "Message_Template_Price_Confirmation", "Message_Template_Shortage"}
    updates = {k: str(v) for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "لم يتم إرسال أي قالب للتحديث"}), 400
    settings = db.update_settings(updates)
    return jsonify({"success": True, "templates": {k: settings.get(k, "") for k in allowed}})


@app.post("/api/message-templates/reset")
def api_reset_message_templates():
    from db import DEFAULT_SETTINGS
    reset = {k: v for k, v in DEFAULT_SETTINGS.items() if k.startswith("Message_Template_")}
    settings = db.update_settings(reset)
    return jsonify({"success": True, "templates": reset})


@app.post("/api/data/reset")
def api_reset_all_data():
    data=request.get_json(silent=True) or {}
    confirmation=str(data.get("confirmation") or "").strip()
    if confirmation != "حذف كل البيانات":
        return jsonify({"error":"للتأكيد اكتب: حذف كل البيانات"}),400
    try:
        return jsonify(db.reset_all_data())
    except Exception as e:
        return jsonify({"error":f"تعذر مسح البيانات: {e}"}),500

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # Local backend serves files from disk; cloud backend stores image bytes in PostgreSQL.
    getter = getattr(db, "get_uploaded_image", None)
    if getter:
        item = getter(filename)
        if not item:
            return jsonify({"error":"الصورة غير موجودة"}), 404
        return send_file(io.BytesIO(item["data"]), mimetype=item["content_type"], download_name=item.get("filename") or "image")
    from db import UPLOAD_DIR
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/orders", methods=["GET"])
def api_list_orders():
    orders=db.get_all_orders(); q=(request.args.get("q") or "").strip().lower(); status=(request.args.get("status") or "").strip()
    date_from=(request.args.get("date_from") or "").strip(); date_to=(request.args.get("date_to") or "").strip()
    if q:
        qp=clean_phone(q)
        def match(o):
            blob=" ".join([str(o.get("Customer_Name","")),str(o.get("Phone","")),str(o.get("Product_Name","")),str(o.get("Order_ID",""))]).lower()
            item_match=any(q in str(i.get("Product_Name","")) .lower() for i in o.get("Items",[]))
            return q in blob or (qp and qp in str(o.get("Phone",""))) or item_match
        orders=[o for o in orders if match(o)]
    if status: orders=[o for o in orders if o.get("Status")==status]
    if date_from: orders=[o for o in orders if str(o.get("Order_Date",""))>=date_from]
    if date_to: orders=[o for o in orders if str(o.get("Order_Date",""))<=date_to]
    orders.sort(key=lambda o:str(o.get("Created_At","")), reverse=True)
    return jsonify({"orders":orders,"count":len(orders)})

@app.route("/api/orders/search", methods=["GET"])
def api_search_orders(): return api_list_orders()

@app.route("/api/orders/<order_id>", methods=["GET"])
def api_get_order(order_id):
    o=db.get_order(order_id)
    if not o: return jsonify({"error":"الطلب غير موجود"}),404
    return jsonify({"order":o,"activity_log":db.get_activity_log(order_id),"undo":db.get_undo_info(order_id)})

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data=request.get_json(silent=True) or {}; errors=validate_order_payload(data)
    if errors: return jsonify({"errors":errors}),400
    products,_=validate_products(data)
    try:
        order=db.create_order(data["customer_name"].strip(), clean_phone(data["phone"]), products, str(data.get("notes") or "").strip(), str(data.get("order_date") or "").strip() or None)
    except Exception as e:
        return jsonify({"error":f"تعذر حفظ الطلب: {e}"}),500
    return jsonify({"order":order}),201

@app.route("/api/orders/<order_id>", methods=["PUT"])
def api_update_order(order_id):
    data=request.get_json(silent=True) or {}; errors=validate_order_payload(data, partial=True)
    if errors:return jsonify({"errors":errors}),400
    fields={"Customer_Name":str(data["customer_name"]).strip() if "customer_name" in data else None,
            "Phone":clean_phone(data["phone"]) if "phone" in data else None,
            "Notes":str(data.get("notes") or "") if "notes" in data else None,
            "Order_Date":str(data.get("order_date") or "") if "order_date" in data else None}
    fields={k:v for k,v in fields.items() if v is not None}
    if data.get("status") in ALL_STATUSES: fields["Status"]=data["status"]
    products=data.get("products") if "products" in data or "product_name" in data or "quantity" in data else None
    if products is not None and "products" not in data: products=[{"product_name":data.get("product_name"),"quantity":data.get("quantity")}]
    try: order=db.update_order(order_id,fields,products)
    except ValueError as e:return jsonify({"error":str(e)}),400
    except Exception as e:return jsonify({"error":f"تعذر تعديل الطلب: {e}"}),500
    if order is None:return jsonify({"error":"الطلب غير موجود"}),404
    return jsonify({"order":order})

@app.route("/api/orders/<order_id>", methods=["DELETE"])
def api_delete_order(order_id):
    try:
        ok=db.delete_order(order_id)
    except Exception as e:
        return jsonify({"error":f"تعذر حذف الطلب: {e}"}),500
    if not ok:return jsonify({"error":"الطلب غير موجود"}),404
    return jsonify({"success":True})


@app.post("/api/orders/<order_id>/items/<item_id>/image")
def api_upload_item_image(order_id, item_id):
    f = request.files.get("image")
    if not f or not f.filename:
        return jsonify({"error":"لم يتم اختيار صورة"}),400
    try:
        rel = db.set_item_image(order_id, item_id, f.stream, f.filename, request.content_length)
    except ValueError as e:
        return jsonify({"error":str(e)}),400
    except Exception as e:
        return jsonify({"error":f"تعذر حفظ الصورة: {e}"}),500
    if rel is None:
        return jsonify({"error":"المنتج غير موجود داخل الطلب"}),404
    return jsonify({"success":True,"path":rel,"url":f"/uploads/{rel}"})

@app.delete("/api/orders/<order_id>/items/<item_id>/image")
def api_delete_item_image(order_id, item_id):
    try:
        ok=db.delete_item_image(order_id,item_id)
    except Exception as e:
        return jsonify({"error":f"تعذر حذف الصورة: {e}"}),500
    if not ok:return jsonify({"error":"المنتج غير موجود"}),404
    return jsonify({"success":True})


def result_response(result):
    return jsonify(result), result.get("code",200) if "error" in result else 200

@app.post("/api/orders/<order_id>/availability")
def api_availability(order_id):
    data=request.get_json(silent=True) or {}
    updates=data.get("items") or []
    if not isinstance(updates,list) or not updates:
        return jsonify({"error":"أرسل حالة توفر المنتجات"}),400
    return result_response(db.set_availability(order_id, updates, data.get("available_date") or None))

@app.post("/api/orders/<order_id>/available")
def api_available_compat(order_id):
    return result_response(db.mark_available(order_id,(request.get_json(silent=True) or {}).get("available_date") or None))

@app.post("/api/orders/<order_id>/undo")
def api_undo(order_id): return result_response(db.undo_last(order_id))

@app.post("/api/orders/<order_id>/contact")
def api_contact(order_id):
    data=request.get_json(silent=True) or {}
    try: days=int(data.get("followup_days",2))
    except (TypeError,ValueError): days=2
    return result_response(db.mark_contacted(order_id,days))

@app.post("/api/orders/<order_id>/contact-status")
def api_contact_status(order_id):
    data=request.get_json(silent=True) or {}
    return result_response(db.set_contact_status(order_id, str(data.get("contact_status") or ""), str(data.get("note") or ""), rejected_item_ids=data.get("rejected_item_ids") or []))

@app.post("/api/orders/<order_id>/pickup")
def api_pickup(order_id): return result_response(db.mark_pickup(order_id,bool((request.get_json(silent=True) or {}).get("force"))))

@app.post("/api/orders/<order_id>/not-picked")
def api_not_picked(order_id): return result_response(db.mark_not_picked(order_id))

@app.post("/api/orders/<order_id>/postpone")
def api_postpone(order_id):
    data=request.get_json(silent=True) or {}; days=data.get("days"); custom=data.get("custom_date")
    try: days=int(days) if days is not None else None
    except (TypeError,ValueError): return jsonify({"error":"قيمة الأيام غير صحيحة"}),400
    return result_response(db.postpone(order_id,days,custom or None))

@app.post("/api/orders/<order_id>/cancel")
def api_cancel(order_id): return result_response(db.cancel_order(order_id,str((request.get_json(silent=True) or {}).get("note") or "")))


ACTION_CENTER_LABELS = {
    "overdue": "متأخرة",
    "needs_supply": "تحتاج توفير",
    "awaiting_reply": "تنتظر رد العميل",
    "today": "متابعة اليوم",
}

def _action_center_item(order, today):
    status = str(order.get("Status") or "").strip()
    contact = str(order.get("Contact_Status") or "").strip()
    next_followup = str(order.get("Next_Followup_Date") or "").strip()

    if status in CLOSED_STATUSES:
        return None

    if ((contact == CONTACT_AWAITING) or status in (STATUS_CONTACTED, STATUS_NOT_PICKED)) and next_followup and next_followup < today:
        hint = "موعد المتابعة تجاوز اليوم"
        try:
            due = date.fromisoformat(next_followup)
            now = date.fromisoformat(today)
            hint = f"متأخر منذ {max(1, (now - due).days)} يوم"
        except ValueError:
            pass
        return {"action_key":"overdue","priority":0,"next_action":"متابعة عاجلة","action_hint":hint}

    if next_followup == today and (contact == CONTACT_AWAITING or status in (STATUS_CONTACTED, STATUS_NOT_PICKED)):
        return {"action_key":"today","priority":1,"next_action":"متابعة العميل","action_hint":"موعد المتابعة اليوم"}

    if contact == CONTACT_AWAITING:
        return {"action_key":"awaiting_reply","priority":2,"next_action":"انتظار رد العميل","action_hint":"الرسالة أُرسلت وننتظر رد العميل"}

    if status == STATUS_PENDING:
        return {"action_key":"needs_supply","priority":3,"next_action":"متابعة التوفير","action_hint":"يوجد منتج أو أكثر بانتظار التوفر"}

    return None

@app.get("/api/action-center")
def api_action_center():
    orders = db.get_all_orders()
    today = today_str()
    grouped = {key: [] for key in ACTION_CENTER_LABELS}
    for order in orders:
        item = _action_center_item(order, today)
        if not item:
            continue
        row = dict(order)
        row.update(item)
        grouped[item["action_key"]].append(row)

    for key in grouped:
        grouped[key].sort(key=lambda x: (
            int(x.get("priority", 99)),
            str(x.get("Next_Followup_Date") or "9999-99-99"),
            str(x.get("Created_At") or ""),
        ))

    flat = []
    for key in ("overdue", "today", "awaiting_reply", "needs_supply"):
        flat.extend(grouped[key])

    return jsonify({
        "summary": {key: len(grouped[key]) for key in ACTION_CENTER_LABELS},
        "total_actionable": len(flat),
        "items": flat[:50],
        "updated_at": datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M:%S"),
    })

@app.get("/api/dashboard")
def api_dashboard():
    orders=db.get_all_orders(); today=today_str()
    def count(p): return sum(1 for o in orders if p(o))
    stats={
        "total":len(orders),
        "pending":count(lambda o:o["Status"]==STATUS_PENDING),
        "available":count(lambda o:o["Status"] in (STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE) and o.get("Contact_Status") in ("", CONTACT_NOT_CONTACTED)),
        "awaiting_reply":count(lambda o:o.get("Contact_Status")==CONTACT_AWAITING),
        "pickup_pending":count(lambda o:o["Status"] in (STATUS_CONTACTED, STATUS_NOT_PICKED)),
        "picked_up":count(lambda o:o["Status"]==STATUS_PICKED_UP),
        "today_followup":count(lambda o: ((o["Status"] in (STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE) and o.get("Contact_Status") in ("", CONTACT_NOT_CONTACTED)) or o.get("Contact_Status")==CONTACT_AWAITING or o["Status"] in (STATUS_CONTACTED, STATUS_NOT_PICKED)) and str(o.get("Next_Followup_Date") or "")==today),
        "overdue":count(lambda o: ((o.get("Contact_Status")==CONTACT_AWAITING) or o["Status"] in (STATUS_CONTACTED, STATUS_NOT_PICKED)) and str(o.get("Next_Followup_Date") or "") and str(o.get("Next_Followup_Date"))<today),
        "date":today,
    }
    return jsonify(stats)

def active_followups(orders):
    today=today_str(); out=[]
    for o in orders:
        if o["Status"] in CLOSED_STATUSES: continue
        if o["Status"] in (STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE): out.append((o,"needs_call"))
        elif o["Status"] in (STATUS_CONTACTED,STATUS_NOT_PICKED):
            n=str(o.get("Next_Followup_Date") or "")
            if n and n<today:out.append((o,"overdue"))
            elif n==today:out.append((o,"today"))
    priority={"overdue":0,"today":1,"needs_call":2}; out.sort(key=lambda x:(priority[x[1]],str(x[0].get("Created_At",""))))
    return out

@app.get("/api/followups/today")
def api_followups_today():
    payload=[]
    for o,kind in active_followups(db.get_all_orders()):
        x=dict(o); x["_followup_kind"]=kind; payload.append(x)
    return jsonify({"followups":payload,"count":len(payload)})

@app.get("/api/followups/overdue")
def api_followups_overdue():
    today=today_str(); items=[o for o in db.get_all_orders() if o["Status"] in (STATUS_CONTACTED,STATUS_NOT_PICKED) and str(o.get("Next_Followup_Date") or "") and str(o.get("Next_Followup_Date"))<today]
    items.sort(key=lambda o:str(o.get("Next_Followup_Date",""))); return jsonify({"followups":items,"count":len(items)})


def _whatsapp_clean_products(order):
    items = order.get("Items") or []
    if not items and order.get("Product_Name"):
        items = [{"Product_Name": order.get("Product_Name"), "Quantity": order.get("Quantity") or 1}]
    return items


def _money(v):
    return str(v).strip() if v not in (None, "") else ""

def _template_fill(template, values):
    text = str(template or "")
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value or ""))
    return text.strip()


def _format_available_items(items):
    lines = []
    for i in items:
        line = f"• {i.get('Product_Name','')} × {i.get('Quantity') or 1}"
        normal = _money(i.get('Available_Price')); disc = _money(i.get('Discounted_Price'))
        if normal: line += f" — السعر {normal} ريال"
        if disc: line += f" — بعد الخصم {disc} ريال"
        lines.append(line)
    return "\n".join(lines)


def _format_unavailable_items(items):
    lines = []
    for i in items:
        reason = str(i.get('Unavailable_Reason') or '').strip()
        line = f"• {i.get('Product_Name','')} × {i.get('Quantity') or 1}"
        if reason: line += f" — {reason}"
        lines.append(line)
    return "\n".join(lines)


def whatsapp_customer_message(order):
    settings = db.get_settings()
    pharmacy = settings.get("Pharmacy_Name", "صيدلية عز الصحة")
    items = order.get("Items") or []
    legacy_rejected = (order.get("Status") == STATUS_CANCELLED
                       and order.get("Contact_Status") == CONTACT_REJECTED
                       and any(i.get("Availability_Status") == "بانتظار التوفر" for i in items))
    eligible = [i for i in items
                if str(i.get("Customer_Decision") or "").strip() != "rejected"
                and not (legacy_rejected and i.get("Availability_Status") != "بانتظار التوفر")]
    available = [i for i in eligible if i.get("Availability_Status") == "متوفر"]
    unavailable = [i for i in eligible if i.get("Availability_Status") == "غير متوفر"]
    if not available and not unavailable:
        available = eligible

    products_available = _format_available_items(available)
    products_unavailable = _format_unavailable_items(unavailable)
    price_confirmation = any(str(i.get("Price_Confirmation_Required") or "").strip() in {"نعم", "1", "true", "True"} for i in available)
    values = {
        "اسم_العميل": order.get("Customer_Name", ""),
        "اسم_الصيدلية": pharmacy,
        "رقم_الطلب": order.get("Order_ID", ""),
        "التاريخ": today_str(),
        "المنتجات_المتوفرة": products_available,
        "المنتجات_غير_المتوفرة": products_unavailable,
        "الإجمالي": "",
        "الشعار": settings.get("Tagline", "رعاية من القلب"),
    }
    if price_confirmation and available:
        template = settings.get("Message_Template_Price_Confirmation")
    elif unavailable and available:
        template = settings.get("Message_Template_Partial")
    elif unavailable and not available:
        template = settings.get("Message_Template_Unavailable")
    else:
        template = settings.get("Message_Template_Available")
    if not template:
        template = settings.get("Message_Template_Available", "السلام عليكم {اسم_العميل} 🌷\n\nمعك {اسم_الصيدلية}.\n\n{المنتجات_المتوفرة}")
    return _template_fill(template, values)

@app.get("/api/whatsapp/order/<order_id>")
def api_whatsapp_order(order_id):
    order = db.get_order(order_id)
    if not order:
        return jsonify({"error":"الطلب غير موجود"}),404
    message = whatsapp_customer_message(order)
    phone = clean_phone(order.get("Phone"))
    wa_url = f"https://wa.me/{phone}?text=" + quote(message)
    app_url = f"whatsapp://send?phone={phone}&text=" + quote(message)
    return jsonify({"order_id":order_id,"phone":phone,"message":message,"url":app_url,"web_url":wa_url})


def _open_whatsapp_app(url):
    return False


@app.post("/api/whatsapp/open/<order_id>")
def api_open_whatsapp_order(order_id):
    order = db.get_order(order_id)
    if not order:
        return jsonify({"error":"الطلب غير موجود"}),404
    message = whatsapp_customer_message(order)
    phone = clean_phone(order.get("Phone"))
    if not phone:
        return jsonify({"error":"رقم جوال العميل غير صالح"}),400
    app_url = f"whatsapp://send?phone={phone}&text=" + quote(message)
    web_url = f"https://wa.me/{phone}?text=" + quote(message)
    try:
        db.set_contact_status(order_id, CONTACT_AWAITING, "تم تجهيز رسالة WhatsApp للعميل، بانتظار الرد")
    except Exception:
        pass
    return jsonify({"success":True,"message":message,"url":app_url,"web_url":web_url})


@app.post("/api/whatsapp/open-shortages")
def api_open_whatsapp_shortages():
    d = api_whatsapp_shortages().get_json()
    message = d.get("message", "")
    url = "whatsapp://send?text=" + quote(message)
    return jsonify({"success":True,"message":message,"url":url,"web_url":"https://web.whatsapp.com/"})


def render_shortage_message(message_body, pharmacy=None):
    settings = db.get_settings()
    pharmacy = pharmacy or settings.get("Pharmacy_Name", "صيدلية عز الصحة")
    values = {
        "اسم_الصيدلية": pharmacy,
        "التاريخ": today_str(),
        "النواقص": message_body or "لا توجد نواقص مسجلة حاليًا ✅",
        "الشعار": settings.get("Tagline", "رعاية من القلب"),
    }
    template = settings.get("Message_Template_Shortage") or "📦 نواقص العملاء – {اسم_الصيدلية}\nالتاريخ: {التاريخ}\n\n{النواقص}\n\nفضلاً توفير الكميات أعلاه عند الإمكان.\n{الشعار} 💙"
    return _template_fill(template, values)


@app.get("/api/whatsapp/shortages")
def api_whatsapp_shortages():
    orders = db.get_all_orders()
    orders = [o for o in orders if any(i.get("Availability_Status") == "بانتظار التوفر" for i in (o.get("Items") or [])) or o.get("Status") == STATUS_PENDING]
    orders.sort(key=lambda o: str(o.get("Created_At", "")), reverse=True)
    body_lines=[]
    for o in orders:
        body_lines.append(f"• {o.get('Customer_Name','')} — {o.get('Order_ID','')}")
        for i in (o.get("Items") or []):
            if i.get("Availability_Status") == "بانتظار التوفر":
                body_lines.append(f"  - {i.get('Product_Name','')} × {i.get('Quantity') or 1}")
    body = "\n".join(body_lines)
    message = render_shortage_message(body)
    return jsonify({"orders":orders,"count":len(orders),"message":message})

@app.get("/api/whatsapp/shortages/grouped")
def api_whatsapp_shortages_grouped():
    orders = api_whatsapp_shortages().get_json().get("orders", [])
    grouped = {}
    for o in orders:
        for i in (o.get("Items") or []):
            if i.get("Availability_Status") != "بانتظار التوفر":
                continue
            key = str(i.get("Product_Name") or "").strip().lower()
            row = grouped.setdefault(key, {"Product_Name": i.get("Product_Name",""), "Quantity": 0, "Orders": 0})
            row["Quantity"] += int(i.get("Quantity") or 1)
            row["Orders"] += 1
    items = sorted(grouped.values(), key=lambda x: (-x["Quantity"], str(x["Product_Name"]).lower()))
    body = "\n".join(f"{idx}. {x['Product_Name']} — إجمالي المطلوب: {x['Quantity']} ({x['Orders']} طلب)" for idx, x in enumerate(items, 1))
    return jsonify({"items": items, "count": len(items), "message": render_shortage_message(body)})


# ---------------------------------------------------------------------------
# Customer Shortages
# ---------------------------------------------------------------------------

def _customer_shortage_items(order):
    """
    Single source of truth for customer shortages.

    Priority:
    1) Item-level availability_status == "بانتظار التوفير".
    2) For legacy/inconsistent orders whose order status is still pending,
       fall back to all non-rejected items.
    """
    items = list(order.get("Items") or [])

    active_items = [
        item for item in items
        if str(item.get("Customer_Decision") or "").strip().lower() != "rejected"
    ]

    pending_items = [
        item for item in active_items
        if str(item.get("Availability_Status") or "").strip() == "بانتظار التوفير"
    ]

    if pending_items:
        return pending_items

    # Legacy order records may have no item rows at all.
    if not items and str(order.get("Status") or "").strip() == STATUS_PENDING:
        return [{
            "Item_ID": "",
            "Product_Name": order.get("Product_Name") or "",
            "Quantity": order.get("Quantity") or 1,
            "Availability_Status": STATUS_PENDING,
            "Customer_Decision": "",
        }]

    # If the order itself is still pending but item-level statuses are stale,
    # treat all non-rejected items as customer shortages.
    if str(order.get("Status") or "").strip() == STATUS_PENDING:
        return active_items

    return []


@app.get("/api/customer-shortages")
def api_customer_shortages():
    denied = _daily_shortage_auth()
    if denied:
        return denied

    try:
        rows = []
        for order in db.get_all_orders():
            shortage_items = _customer_shortage_items(order)

            for item in shortage_items:
                rows.append({
                    "type": "customer",
                    "order_id": order.get("Order_ID") or "",
                    "customer_name": order.get("Customer_Name") or "",
                    "phone": order.get("Phone") or "",
                    "product_name": item.get("Product_Name") or order.get("Product_Name") or "",
                    "quantity": item.get("Quantity") or order.get("Quantity") or 1,
                    "order_date": order.get("Order_Date") or order.get("Created_At") or "",
                    "status": "بانتظار التوفير",
                })

        rows.sort(key=lambda row: str(row.get("order_date") or ""), reverse=True)
        return jsonify({
            "shortages": rows,
            "count": len(rows),
            "order_count": len({row["order_id"] for row in rows if row.get("order_id")})
        })
    except Exception as e:
        return jsonify({"error": f"تعذر قراءة نواقص العملاء: {e}"}), 500

def _daily_shortage_actor():
    provider = getattr(db, "_auth_user_provider", None)
    if provider:
        try:
            user = provider()
            if user:
                return str(user.get("name") or user.get("username") or "موظف")
        except Exception:
            pass
    return str(session.get("username") or "موظف")

def _daily_shortage_auth():
    provider = getattr(db, "_auth_user_provider", None)
    if provider:
        try:
            if provider():
                return None
        except Exception:
            pass
    if session.get("authenticated") or session.get("user_id"):
        return None
    return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401

@app.get("/api/pharmacy-shortages")
def api_pharmacy_shortages():
    denied = _daily_shortage_auth()
    if denied: return denied
    try:
        ensure_pharmacy_shortage_schema()
        return jsonify({"shortages": list_pharmacy_shortages(), "stats": pharmacy_shortage_stats()})
    except Exception as e:
        return jsonify({"error":f"تعذر قراءة نواقص الصيدلية: {e}"}),500

@app.post("/api/pharmacy-shortages")
def api_create_pharmacy_shortage():
    denied = _daily_shortage_auth()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    try:
        ensure_pharmacy_shortage_schema()
        row = create_pharmacy_shortage(data.get("product_name"), data.get("quantity"), data.get("note", ""), _daily_shortage_actor())
        return jsonify({"shortage":row}),201
    except ValueError as e:
        return jsonify({"error":str(e)}),400
    except Exception as e:
        return jsonify({"error":f"تعذر إضافة نقص الصيدلية: {e}"}),500

@app.put("/api/pharmacy-shortages/<shortage_id>")
def api_update_pharmacy_shortage(shortage_id):
    denied = _daily_shortage_auth()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    try:
        ensure_pharmacy_shortage_schema()
        row = update_pharmacy_shortage(shortage_id, data.get("product_name"), data.get("quantity"), data.get("note"), _daily_shortage_actor())
        if row is None: return jsonify({"error":"النقص غير موجود"}),404
        return jsonify({"shortage":row})
    except (ValueError, TypeError):
        return jsonify({"error":"اسم المنتج مطلوب والكمية يجب أن تكون رقمًا صحيحًا أكبر من صفر"}),400
    except Exception as e:
        return jsonify({"error":f"تعذر تعديل النقص: {e}"}),500

@app.post("/api/pharmacy-shortages/<shortage_id>/available")
def api_pharmacy_shortage_available(shortage_id):
    denied = _daily_shortage_auth()
    if denied: return denied
    try:
        ensure_pharmacy_shortage_schema()
        row = set_pharmacy_shortage_available(shortage_id, _daily_shortage_actor())
        if row is None: return jsonify({"error":"النقص غير موجود"}),404
        return jsonify({"shortage":row})
    except Exception as e:
        return jsonify({"error":f"تعذر تغيير حالة النقص: {e}"}),500

@app.post("/api/pharmacy-shortages/<shortage_id>/undo")
def api_pharmacy_shortage_undo(shortage_id):
    denied = _daily_shortage_auth()
    if denied: return denied
    try:
        ensure_pharmacy_shortage_schema()
        return result_response(undo_pharmacy_shortage(shortage_id, _daily_shortage_actor()))
    except Exception as e:
        return jsonify({"error":f"تعذر التراجع عن النقص: {e}"}),500

@app.get("/api/pharmacy-shortages/whatsapp")
def api_pharmacy_shortages_whatsapp():
    denied = _daily_shortage_auth()
    if denied: return denied
    kind = (request.args.get("kind") or "all").strip().lower()
    if kind not in {"customer", "pharmacy", "all"}:
        return jsonify({"error":"نوع الإرسال غير صحيح"}),400
    ensure_pharmacy_shortage_schema()
    customer_lines=[]
    customer_item_count=0
    customer_order_count=0
    for order in db.get_all_orders():
        shortage_items = _customer_shortage_items(order)
        if not shortage_items:
            continue

        customer_order_count += 1
        customer_lines.append(f"• {order.get('Customer_Name','')} — {order.get('Order_ID','')}")
        order_note = str(order.get("Notes") or "").strip()
        if order_note:
            customer_lines.append(f"  📝 الملاحظة: {order_note}")

        for item in shortage_items:
            customer_item_count += 1
            customer_lines.append(
                f"  - {item.get('Product_Name') or order.get('Product_Name','')} × {item.get('Quantity') or order.get('Quantity') or 1}"
            )
    pharmacy_rows=[r for r in list_pharmacy_shortages() if r.get("status")=="pending"]
    pharmacy_lines=[]
    for r in pharmacy_rows:
        line = f"• {r['product_name']} × {r['quantity']}"
        note = str(r.get("note") or "").strip()
        if note:
            line += f" — 📝 الملاحظة: {note}"
        pharmacy_lines.append(line)
    sections=[]
    if kind in {"customer","all"}:
        sections.append("نواقص العملاء:\n" + ("\n".join(customer_lines) if customer_lines else "لا توجد نواقص عملاء حاليًا ✅"))
    if kind in {"pharmacy","all"}:
        sections.append("نواقص الصيدلية:\n" + ("\n".join(pharmacy_lines) if pharmacy_lines else "لا توجد نواقص صيدلية حاليًا ✅"))
    message="النواقص اليومية\n\n" + "\n\n".join(sections)
    return jsonify({"message":message,"customer_count":customer_order_count,"customer_item_count":customer_item_count,"pharmacy_count":len(pharmacy_rows)})


@app.post("/api/import-data")
def api_import_data():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error":"اختر ملف Excel أو نسخة احتياطية"}),400
    filename = str(f.filename).lower()
    if not filename.endswith((".xlsx", ".zip")):
        return jsonify({"error":"يسمح فقط بملفات .xlsx أو .zip"}),400
    import tempfile, os
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="ezz_import_", suffix=".zip" if filename.endswith(".zip") else ".xlsx")
        os.close(fd)
        f.save(temp_path)
        result = db.import_legacy_data(temp_path)
        return jsonify({"success":True, "message":"تم استيراد البيانات بنجاح", **result})
    except ValueError as e:
        return jsonify({"error":str(e)}),400
    except Exception as e:
        return jsonify({"error":f"تعذر استيراد البيانات: {e}"}),500
    finally:
        if temp_path:
            try: os.remove(temp_path)
            except OSError: pass


@app.get("/api/backups")
def api_backups(): return jsonify({"backups":db.list_backups()})

@app.post("/api/backups")
def api_backup():
    try: name=db.create_manual_backup()
    except Exception as e:return jsonify({"error":f"تعذر إنشاء النسخة: {e}"}),500
    return (jsonify({"success":True,"filename":name}),200) if name else (jsonify({"error":"تعذر إنشاء النسخة"}),500)

@app.post("/api/backups/restore")
def api_restore():
    fn=str((request.get_json(silent=True) or {}).get("filename") or "").strip()
    if not fn:return jsonify({"error":"يرجى تحديد النسخة"}),400
    try: ok=db.restore_backup(fn)
    except ValueError as e:return jsonify({"error":str(e)}),400
    except Exception as e:return jsonify({"error":f"تعذر الاستعادة: {e}"}),500
    return (jsonify({"success":True}),200) if ok else (jsonify({"error":"النسخة غير موجودة"}),404)


# Register the PostgreSQL Excel export endpoint directly in the Flask app.
# This is the cloud-safe export used by the existing backup-page button.
try:
    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)
except Exception as exc:
    app.logger.exception("Failed to register Excel export route: %s", exc)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error":"حجم الصورة أكبر من الحد المسموح به (10 ميجابايت)"}),413

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error":"حدث خطأ داخلي في الخادم"}), 500
    return Response("حدث خطأ داخلي في الخادم", status=500, mimetype="text/plain; charset=utf-8")

if __name__ == "__main__":
    def open_browser():
        try:webbrowser.open("http://127.0.0.1:5000")
        except Exception:pass
    threading.Timer(1.2,open_browser).start()
    app.run(debug=False,host="0.0.0.0",port=5000)
