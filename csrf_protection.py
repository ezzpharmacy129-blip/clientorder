# -*- coding: utf-8 -*-
"""Central CSRF protection for the authenticated Flask application."""
import hmac
import secrets

from flask import jsonify, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOGOUT_GET = ("/logout", "GET")


def install_csrf(app):
    """Install a session-bound synchronizer-token CSRF check for unsafe requests."""
    if getattr(app, "_ezz_csrf_installed", False):
        return
    app._ezz_csrf_installed = True

    def csrf_token():
        token = str(session.get("_csrf_token") or "").strip()
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    app.context_processor(lambda: {"csrf_token": csrf_token})

    @app.before_request
    def enforce_csrf():
        if request.method in SAFE_METHODS:
            return None
        # Keep the existing public GET logout link behavior. Data-changing APIs
        # and POST logout remain protected by the synchronizer token below.
        if (request.path, request.method) == LOGOUT_GET:
            return None

        expected = str(session.get("_csrf_token") or "").strip()
        supplied = str(
            request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token")
            or ""
        ).strip()

        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            return jsonify({
                "error": "طلب غير صالح. أعد تحميل الصفحة ثم حاول مرة أخرى.",
                "code": "csrf_failed",
            }), 403
        return None

    app.extensions["ezz_csrf"] = {
        "token": csrf_token,
    }
