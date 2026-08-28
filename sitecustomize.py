# -*- coding: utf-8 -*-
"""Install the single-user login before the application's routes are served.

The original Render command remains `gunicorn app:app`.  Importing app from
sitecustomize caused a circular import, so instead we hook Flask's constructor
and attach the authentication middleware immediately when the app is created.
"""
import base64
import hashlib
import html
import hmac
import os
import time
from collections import defaultdict, deque

_AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
_AUTH_HASH = os.environ.get("AUTH_PASSWORD_HASH", "")
_SECRET_KEY = os.environ.get("SECRET_KEY", "")


def _verify_password(password: str, encoded: str) -> bool:
    try:
        method, iterations_s, salt_s, digest_s = encoded.split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = base64.urlsafe_b64decode(salt_s + "=" * (-len(salt_s) % 4))
        expected = base64.urlsafe_b64decode(digest_s + "=" * (-len(digest_s) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

_attempts = defaultdict(deque)
_WINDOW = 600
_MAX_ATTEMPTS = 5
_INSTALLED_ATTR = "_ezz_auth_installed"


def _login_page(error=""):
    err = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return f'''<!doctype html>
<html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>تسجيل الدخول - صيدلية عز الصحة</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f7fb;font-family:Tahoma,Arial,sans-serif;color:#18324a}}
.card{{width:min(420px,92vw);background:#fff;border-radius:22px;padding:30px;box-shadow:0 18px 60px rgba(20,50,80,.14);border:1px solid #e6edf4}}
.logo{{width:72px;height:72px;border-radius:18px;display:block;margin:0 auto 18px;object-fit:contain}}
h1{{font-size:23px;text-align:center;margin:0 0 6px}}p{{text-align:center;color:#6b7b8c;margin:0 0 24px}}
label{{display:block;font-weight:700;margin:14px 0 7px}}input{{width:100%;padding:13px 14px;border:1px solid #ccd7e2;border-radius:12px;font-size:16px;outline:none}}
input:focus{{border-color:#277aa8;box-shadow:0 0 0 3px rgba(39,122,168,.1)}}button{{width:100%;margin-top:20px;border:0;border-radius:12px;padding:13px;background:#1e6f95;color:#fff;font-size:16px;font-weight:700;cursor:pointer}}
.error{{background:#fff0f0;color:#a62b2b;border:1px solid #f3c6c6;padding:10px 12px;border-radius:10px;margin-bottom:14px;font-size:14px}}
.small{{font-size:12px;color:#94a0ac;text-align:center;margin-top:18px}}
</style></head><body><div class="card">
<img class="logo" src="/static/logo-mark.png" alt="شعار صيدلية عز الصحة">
<h1>صيدلية عز الصحة</h1><p>تسجيل الدخول إلى نظام متابعة الطلبات</p>{err}
<form method="post" action="/login"><label for="username">اسم المستخدم</label>
<input id="username" name="username" autocomplete="username" required>
<label for="password">كلمة المرور</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">دخول</button></form>
<div class="small">الوصول إلى النظام مخصص للمستخدم المصرح له فقط.</div>
</div></body></html>'''


def _install_auth(app):
    if getattr(app, _INSTALLED_ATTR, False):
        return
    setattr(app, _INSTALLED_ATTR, True)
    app.secret_key = _SECRET_KEY or os.urandom(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=12 * 60 * 60,
    )

    from flask import jsonify, redirect, request, session, url_for

    def login():
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        now = time.time()
        q = _attempts[client_ip]
        while q and now - q[0] > _WINDOW:
            q.popleft()
        if request.method == "GET":
            if session.get("authenticated"):
                return redirect(url_for("index"))
            return _login_page()
        if len(q) >= _MAX_ATTEMPTS:
            return _login_page("تم تجاوز عدد المحاولات المسموح بها. حاول لاحقًا."), 429
        q.append(now)
        username = str(request.form.get("username") or "").strip()
        password = str(request.form.get("password") or "")
        if username == _AUTH_USERNAME and _AUTH_HASH and _verify_password(password, _AUTH_HASH):
            session.clear()
            session.permanent = True
            session["authenticated"] = True
            session["username"] = _AUTH_USERNAME
            next_url = request.args.get("next") or url_for("index")
            if not str(next_url).startswith("/"):
                next_url = url_for("index")
            return redirect(next_url)
        return _login_page("اسم المستخدم أو كلمة المرور غير صحيحة."), 401

    app.add_url_rule("/login", "auth_login", login, methods=["GET", "POST"])

    def logout():
        session.clear()
        return redirect(url_for("auth_login"))

    app.add_url_rule("/logout", "auth_logout", logout, methods=["GET", "POST"])

    @app.before_request
    def _require_auth():
        path = request.path
        if path in ("/login", "/logout") or path.startswith("/static/"):
            return None
        if session.get("authenticated"):
            return None
        if path.startswith("/api/"):
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        return redirect(url_for("auth_login", next=request.full_path))

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


# Flask is imported before app.py is loaded. Hook Flask.Flask.__init__ so the
# middleware is attached during creation of the real application object.
try:
    import flask
    _original_flask_init = flask.Flask.__init__

    def _protected_flask_init(self, *args, **kwargs):
        _original_flask_init(self, *args, **kwargs)
        _install_auth(self)

    if not getattr(flask.Flask, "_ezz_auth_constructor_patched", False):
        flask.Flask.__init__ = _protected_flask_init
        flask.Flask._ezz_auth_constructor_patched = True
except Exception:
    pass
