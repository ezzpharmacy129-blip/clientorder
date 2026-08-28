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
        limit = min(max(int(request.args.get("limit", 500)), 1), 2000)
        with db._connect() as conn:
            rows = conn.execute("SELECT created_at,user_name,action,order_id,note,old_status,new_status FROM activity_log ORDER BY created_at DESC LIMIT %s", (limit,)).fetchall()
        return jsonify({"logs":[dict(r) for r in rows]})

    @app.after_request
    def action_audit(response):
        try:
            user = current_user()
            if not user or response.status_code >= 400:
                return response
            path = request.path
            method = request.method
            m = re.match(r"^/api/orders/([^/]+)(?:/|$)", path)
            order_id = m.group(1) if m else ""
            action = None
            if path == "/api/whatsapp/open-shortages":
                action = "WhatsApp"
                order_id = ""
            elif path.startswith("/api/whatsapp/open/"):
                action = "WhatsApp"
            elif path.startswith("/api/whatsapp/order/"):
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
            elif method == "POST" and path.endswith("/available"):
                action = "Mark Available"
            elif method == "POST" and path == "/api/orders":
                action = "Create Order"
            elif method == "PUT" and m:
                action = "Edit Order"
            elif method == "DELETE" and m and "/items/" not in path:
                action = "Delete Order"
            if action:
                # Avoid duplicating the database's detailed operational log for ordinary order actions.
                # The explicit action log is intentionally concise and never contains WhatsApp message text.
                audit(order_id=order_id, action=action, note="تم تنفيذ العملية")
            return response
        except Exception:
            return response
