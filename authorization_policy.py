"""Central production authorization policy.

Normal operational actions remain available to authenticated employees.
Administrative/destructive actions require the admin role. Enforcement is server-side.
"""
from flask import jsonify, request


ADMIN_EXACT = {
    ("POST", "/api/data/reset"),
    ("POST", "/api/backups/restore"),
    ("POST", "/api/import-data"),
}

# Current production permission contract. Values reflect existing business behavior;
# this module is the single server-side authorization source for the admin boundary.
PERMISSION_MATRIX = {
    "employee": {
        "create_order": True, "edit_order": True, "availability": True,
        "contact": True, "whatsapp": True, "pickup": True, "postpone": True,
        "cancel": True, "delete_order": False, "import": False,
        "restore": False, "reset": False, "manage_users": False,
        "view_audit": False,
    },
    "admin": {
        "create_order": True, "edit_order": True, "availability": True,
        "contact": True, "whatsapp": True, "pickup": True, "postpone": True,
        "cancel": True, "delete_order": True, "import": True,
        "restore": True, "reset": True, "manage_users": True,
        "view_audit": True,
    },
}

ADMIN_PREFIXES = (
    "/api/admin/",
    "/admin/",
)


def is_admin_required(path, method):
    method = str(method or "").upper()
    path = str(path or "")
    if (method, path) in ADMIN_EXACT:
        return True
    if path.startswith(ADMIN_PREFIXES):
        return True
    if method == "DELETE" and path.startswith("/api/orders/") and "/items/" not in path and not path.endswith("/image"):
        return True
    return False


def _current_user(app):
    auth = app.extensions.get("ezz_auth") or {}
    provider = auth.get("current_user")
    return provider() if callable(provider) else None


def _is_order_delete(path, method):
    method = str(method or "").upper()
    path = str(path or "")
    return method == "DELETE" and path.startswith("/api/orders/") and "/items/" not in path and not path.endswith("/image")


def _validate_destructive_confirmation():
    if not _is_order_delete(request.path, request.method):
        return None
    data = request.get_json(silent=True) or {}
    confirmation = str(data.get("confirmation") or "").strip()
    if confirmation != "حذف الطلب":
        return jsonify({"error": "للتأكيد اكتب: حذف الطلب"}), 400
    return None


def install_authorization(app):
    if getattr(app, "_ezz_authorization_policy_installed", False):
        return
    app._ezz_authorization_policy_installed = True

    @app.before_request
    def enforce_authorization_policy():
        if not is_admin_required(request.path, request.method):
            return None

        user = _current_user(app)
        if not user:
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        if user.get("role") != "admin":
            return jsonify({"error": "غير مصرح لك بهذا الإجراء"}), 403

        return _validate_destructive_confirmation()

    app.extensions["ezz_authorization"] = {
        "is_admin_required": is_admin_required,
        "permission_matrix": PERMISSION_MATRIX,
    }
