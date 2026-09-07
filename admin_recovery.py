"""Temporary, token-gated emergency recovery for the production admin account."""

import base64
import hashlib
import hmac
import os
import secrets
from flask import abort, jsonify, request


def _hash_password(password):
    iterations = 310000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return f"pbkdf2_sha256${iterations}${enc(salt)}${enc(digest)}"


def install_admin_recovery(app, db):
    token = os.environ.get("ADMIN_RECOVERY_TOKEN", "").strip()
    recovery_password = os.environ.get("ADMIN_RECOVERY_PASSWORD", "")
    if not token or len(token) < 32 or len(recovery_password) < 12:
        return False
    if getattr(app, "_ezz_admin_recovery_installed", False):
        return True

    consumed = {"value": False}

    @app.get("/internal/admin-recovery")
    def admin_recovery():
        presented = request.args.get("token", "")
        if consumed["value"] or not hmac.compare_digest(presented, token):
            abort(404)
        with db._connect() as conn:
            row = conn.execute(
                "UPDATE users SET password_hash=%s, active=TRUE, session_version=COALESCE(session_version,1)+1 WHERE username=%s RETURNING username",
                (_hash_password(recovery_password), "admin"),
            ).fetchone()
        if not row:
            return jsonify({"success": False, "error": "admin user not found"}), 404
        consumed["value"] = True
        return jsonify({"success": True, "username": row["username"], "message": "admin password recovered"})

    app._ezz_admin_recovery_installed = True
    return True
