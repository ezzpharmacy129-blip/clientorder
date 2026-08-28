# -*- coding: utf-8 -*-
import os
import re
import sqlite3
from flask import request, jsonify


def install_security_extensions(app, db):
    if getattr(app, "_ezz_security_extensions", False):
        return
    app._ezz_security_extensions = True
    auth = app.extensions["ezz_auth"]
    current_user = auth["current_user"]
    audit = auth["audit"]

    # The deployed cloud version uses an Excel workbook for application data.
    # Keep the security/admin layer on the same storage model instead of trying
    # to use a PostgreSQL-only connection method that does not exist here.
    def audit_rows(limit=500):
        rows = []
        try:
            from openpyxl import load_workbook
            path = getattr(db, "DB_PATH", "")
            if not path or not os.path.exists(path):
                return rows
            wb = load_workbook(path, read_only=True, data_only=True)
            ws = wb["Activity_Log"] if "Activity_Log" in wb.sheetnames else None
            if ws:
                for r in ws.iter_rows(min_row=2, values_only=True):
                    values = list(r) + [""] * 8
                    rows.append({
                        "created_at": values[6],
                        "user_name": values[7],
                        "action": values[2],
                        "order_id": values[1],
                        "note": values[5],
                        "old_status": values[3],
                        "new_status": values[4],
                    })
            wb.close()
        except Exception:
            return []
        return rows[-max(1, int(limit)):][::-1]

    def users_conn():
        root = os.path.abspath(getattr(db, "SHARED_ROOT", os.path.join(os.path.expanduser("~"), ".ezz_pharmacy_fresh")))
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, "users.sqlite3")
        conn = sqlite3.connect(path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

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
        return jsonify({"logs": audit_rows(limit)})

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

    @app.post("/api/admin/users/<uid>/delete")
    def admin_delete_user(uid):
        user = current_user()
        if not user:
            return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
        if user["role"] != "admin":
            return jsonify({"error":"غير مصرح لك بهذا الإجراء"}), 403
        with users_conn() as conn:
            row = conn.execute("SELECT user_id, username, name, role FROM users WHERE user_id=?", (uid,)).fetchone()
            if not row:
                return jsonify({"error":"المستخدم غير موجود"}), 404
            if uid == user["user_id"]:
                return jsonify({"error":"لا يمكنك حذف حسابك الحالي"}), 400
            conn.execute("DELETE FROM users WHERE user_id=?", (uid,))
        audit(action="Delete User", note=f"حذف المستخدم {row['username']}")
        return jsonify({"success":True})
