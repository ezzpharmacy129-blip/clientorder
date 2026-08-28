# -*- coding: utf-8 -*-
"""Security policy extension for the Excel-backed pharmacy app.
Employees can edit order/customer/product data, while state-changing actions remain admin-only.
"""
from flask import request, jsonify
from auth_security_extensions import install_security_extensions as _base_install

STATE_ADMIN_ONLY = {
    ("POST", "/api/orders/", "availability"),
    ("POST", "/api/orders/", "available"),
    ("POST", "/api/orders/", "undo"),
    ("POST", "/api/orders/", "contact"),
    ("POST", "/api/orders/", "contact-status"),
    ("POST", "/api/orders/", "pickup"),
    ("POST", "/api/orders/", "postpone"),
    ("POST", "/api/orders/", "cancel"),
    ("DELETE", "/api/orders/", "order"),
}


def _is_state_action(path, method):
    if method == "DELETE" and path.startswith("/api/orders/") and "/items/" not in path and not path.endswith("/image"):
        return True
    if method != "POST" or not path.startswith("/api/orders/"):
        return False
    suffixes = ("/availability", "/available", "/undo", "/contact", "/contact-status", "/pickup", "/postpone", "/cancel")
    return path.endswith(suffixes)


def install_security_extensions(app, db):
    _base_install(app, db)
    if getattr(app, "_ezz_security_policy_v2", False):
        return
    app._ezz_security_policy_v2 = True

    auth = app.extensions["ezz_auth"]
    current_user = auth["current_user"]

    @app.before_request
    def enforce_employee_order_edit_policy():
        user = current_user()
        if not user:
            return None

        # Every workflow/state transition is Admin-only.
        if _is_state_action(request.path, request.method):
            if user.get("role") != "admin":
                return jsonify({"error": "تغيير حالة الطلب وصلاحيات التراجع متاحة للمدير فقط"}), 403

        # Employees may edit order information, but never change Status through PUT.
        if request.method == "PUT" and request.path.startswith("/api/orders/"):
            if user.get("role") != "admin":
                data = request.get_json(silent=True) or {}
                if "status" in data:
                    return jsonify({"error": "تغيير حالة الطلب متاح للمدير فقط"}), 403

        return None
