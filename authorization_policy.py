"""Central production authorization policy.

Normal operational actions remain available to authenticated employees.
Administrative/destructive actions require the admin role. Enforcement is server-side.
"""
from functools import wraps
from flask import jsonify, request


ADMIN_EXACT = {
    ("POST", "/api/data/reset"),
    ("POST", "/api/backups/restore"),
    ("POST", "/api/message-templates/reset"),
}

ADMIN_PREFIXES = (
    "/api/admin/",
)

def _current_user(app):
    auth = app.extensions.get("ezz_auth") or {}
    provider = auth.get("current_user")
    return provider() if callable(provider) else None

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
        return None

    app.extensions["ezz_authorization"] = {
        "is_admin_required": is_admin_required,
    }
