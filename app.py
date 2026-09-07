        "اسم_الصيدلية": pharmacy,
        "رقم_الطلب": order.get("Order_ID", ""),
        "التاريخ": today_str(),
        "المنتجات_المتوفرة": products_available,
        "المنتجات_غير_المتوفرة": products_unavailable,
        "الإجمالي": "",
        "الشعار": settings.get("Tagline", "رعاية من القلب"),
    }
    status = str(order.get("Status") or "").strip()
    if status == STATUS_PENDING and not available and not unavailable:
        template = settings.get("Message_Template_Pending")
    elif price_confirmation and available:
        template = settings.get("Message_Template_Price_Confirmation")
    elif unavailable and available:
        template = settings.get("Message_Template_Partial")
    elif unavailable and not available:
        template = settings.get("Message_Template_Unavailable")
    else:
        template = settings.get("Message_Template_Available")
    if not template:
        template = settings.get("Message_Template_Pending" if status == STATUS_PENDING else "Message_Template_Available")
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