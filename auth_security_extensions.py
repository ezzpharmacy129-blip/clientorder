# -*- coding: utf-8 -*-
import re
from flask import request, jsonify


def install_security_extensions(app, db):
    if getattr(app, "_ezz_security_extensions", False):
        return
    app._ezz_security_extensions = True
    auth = app.extensions["ezz_auth"]
    current_user = auth["current_user"]
    audit = auth["audit"]

    @app.before_request
    def admin_data_protection():
        if request.path in ("/api/data/reset", "/api/backups/restore"):
            user = current_user()
            if not user:
                return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
            if user["role"] != "admin":
                return jsonify({"error":"غير مصرح لك بهذا الإجراء"}), 403
        return None

    @app.get("/api/admin/audit")
    def admin_audit_api():
        user = current_user()
        if not user:
            return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
        if user["role"] != "admin":
            return jsonify({"error":"غير مصرح لك بهذا الإجراء"}), 403
        try:
            limit = min(max(int(request.args.get("limit", 500)), 1), 2000)
        except (TypeError, ValueError):
            limit = 500
        with db._connect() as conn:
            rows = conn.execute("SELECT created_at,user_name,action,order_id,note,old_status,new_status FROM activity_log ORDER BY created_at DESC LIMIT %s", (limit,)).fetchall()
        return jsonify({"logs":[dict(r) for r in rows]})

    @app.after_request
    def action_audit(response):
        try:
            user = current_user()
            if not user:
                return response

            # Employees may operate on orders, but must not receive the audit trail embedded in order details.
            if user["role"] != "admin" and request.method == "GET" and re.match(r"^/api/orders/[^/]+$", request.path):
                payload = response.get_json(silent=True)
                if isinstance(payload, dict) and "activity_log" in payload:
                    payload.pop("activity_log", None)
                    response.set_json(payload)

            if response.status_code >= 400:
                return response

            path = request.path
            method = request.method
            m = re.match(r"^/api/orders/([^/]+)(?:/|$)", path)
            order_id = m.group(1) if m else ""
            action = None
            if path == "/api/whatsapp/open-shortages":
                action = "WhatsApp"
                order_id = ""
            elif path.startswith("/api/whatsapp/open/") or path.startswith("/api/whatsapp/order/"):
                action = "WhatsApp"
            elif method == "POST" and path.endswith("/contact"):
                action = "Contact Customer"
            elif method == "POST" and path.endswith("/pickup"):
                action = "Pickup"
            elif method == "POST" and path.endswith("/postpone"):
                action = "Postpone"
            elif method == "POST" and path.endswith("/cancel"):
                action = "Cancel"
            elif method == "POST" and path.endswith("/undo"):
                action = "Undo"
            elif method == "POST" and path.endswith("/availability"):
                action = "Mark Available"
                try:
                    data = request.get_json(silent=True) or {}
                    updates = data.get("items") or []
                    if any(str(x.get("available_price") or "").strip() or str(x.get("discounted_price") or "").strip() for x in updates):
                        audit(order_id=order_id, action="Change Price", note="تم تعديل/تسجيل سعر المنتج")
                    if any(str(x.get("unavailable_reason") or "").strip() for x in updates):
                        audit(order_id=order_id, action="Change Availability Reason", note="تم تسجيل سبب عدم التوفر")
                except Exception:
                    pass
            elif method == "POST" and path.endswith("/available"):
                action = "Mark Available"
            elif method == "POST" and path == "/api/orders":
                action = "Create Order"
            elif method == "PUT" and m:
                action = "Edit Order"
            elif method == "DELETE" and m and "/items/" not in path:
                action = "Delete Order"

            if action:
                audit(order_id=order_id, action=action, note="تم تنفيذ العملية")
            return response
        except Exception:
            return response
