# -*- coding: utf-8 -*-
"""Admin order state controls for the Excel-backed pharmacy app.

Administrators can move an order between availability states in either direction,
including resetting it to "بانتظار التوفر" without restoring a backup.
"""
from flask import request, jsonify
from functools import wraps


def install_admin_order_controls(app, db):
    if getattr(app, "_ezz_admin_order_controls", False):
        return
    app._ezz_admin_order_controls = True
    auth = app.extensions["ezz_auth"]
    current_user = auth["current_user"]

    def admin_only(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
            if user.get("role") != "admin":
                return jsonify({"error": "صلاحية تغيير حالة الطلب متاحة للمدير فقط"}), 403
            return fn(*args, **kwargs)
        return wrapped

    def reset_to_pending(order_id, user):
        from db import _make_backup, _atomic_save, _format_sheet, _lock
        with _lock:
            wb = db._load()
            if "Orders" not in wb.sheetnames or "Order_Items" not in wb.sheetnames:
                wb.close()
                return {"error": "ملف البيانات غير صالح", "code": 500}
            ws = wb["Orders"]
            wi = wb["Order_Items"]
            wl = wb["Activity_Log"]
            wu = wb["Undo_History"]
            old = db._status(ws, order_id)
            if old is None:
                wb.close()
                return {"error": "الطلب غير موجود", "code": 404}
            snapshot = db._row_snapshot(ws, wi, order_id)
            if not snapshot.get("items"):
                wb.close()
                return {"error": "لا توجد منتجات في هذا الطلب", "code": 409}
            _make_backup()
            db._invalidate_undo(wu, order_id)
            for row in wi.iter_rows(min_row=2):
                if str(row[1].value or "") != str(order_id):
                    continue
                row[5].value = "بانتظار التوفر"
                for idx in range(6, 12):
                    row[idx].value = ""
            db._update_fields(ws, order_id, {
                "Status": "بانتظار التوفر",
                "Available_Date": "",
                "Contact_Status": "لم يتم التواصل",
                "Last_Contact_Date": "",
                "Next_Followup_Date": "",
                "Pickup_Date": "",
            })
            db._append_log(wl, order_id, "تعديل حالة التوفر يدويًا", old, "بانتظار التوفر", "تم إرجاع الطلب إلى بانتظار التوفر", user)
            db._add_undo(wu, order_id, "تعديل حالة التوفر يدويًا", snapshot, user)
            for sheet in (ws, wi, wl, wu):
                _format_sheet(sheet)
            _atomic_save(wb)
            try:
                _make_backup("auto")
            except Exception:
                pass
        return {"order": db.get_order(order_id)}

    @app.post("/api/admin/orders/<order_id>/state")
    @admin_only
    def admin_set_order_state(order_id):
        data = request.get_json(silent=True) or {}
        target = str(data.get("status") or "").strip()
        user = current_user()["name"]
        allowed = {
            "بانتظار التوفر": "pending",
            "متوفر - يحتاج اتصال": "available",
            "غير متوفر - يحتاج اتصال": "unavailable",
        }
        if target not in allowed:
            return jsonify({"error": "الحالة المطلوبة غير مدعومة من هذا التعديل الإداري"}), 400
        order = db.get_order(order_id)
        if not order:
            return jsonify({"error": "الطلب غير موجود"}), 404
        items = order.get("Items") or []
        if not items:
            return jsonify({"error": "لا توجد منتجات في الطلب"}), 409
        if target == "بانتظار التوفر":
            return jsonify(reset_to_pending(order_id, user))

        updates = []
        for item in items:
            row = {"Item_ID": item.get("Item_ID"), "availability_status": target}
            if target == "غير متوفر - يحتاج اتصال":
                row["availability_status"] = "غير متوفر"
                row["unavailable_reason"] = str(data.get("reason") or "تعديل يدوي من المدير").strip()
            else:
                row["availability_status"] = "متوفر"
                if data.get("available_price") not in (None, ""):
                    row["available_price"] = data.get("available_price")
                if data.get("discounted_price") not in (None, ""):
                    row["discounted_price"] = data.get("discounted_price")
            updates.append(row)
        result = db.set_availability(order_id, updates, None, user)
        return jsonify(result), result.get("code", 200) if "error" in result else 200
