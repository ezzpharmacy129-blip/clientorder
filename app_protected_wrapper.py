import base64
import hashlib
import hmac
import html
import os
import time
from collections import defaultdict, deque

from flask import jsonify, redirect, request, session, url_for
from app_original import app

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD_HASH = os.environ.get("AUTH_PASSWORD_HASH", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if SECRET_KEY:
    app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=12 * 60 * 60,
)

_attempts = defaultdict(deque)
_WINDOW = 600
_MAX_ATTEMPTS = 5

def verify_password(password):
    try:
        method, iterations_s, salt_s, digest_s = AUTH_PASSWORD_HASH.split("$", 3)
        if method != "pbkdf2_sha256": return False
        iterations = int(iterations_s)
        salt = base64.urlsafe_b64decode(salt_s + "=" * (-len(salt_s) % 4))
        expected = base64.urlsafe_b64decode(digest_s + "=" * (-len(digest_s) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def login_page(error=""):
    err = f'<div style="background:#fff0f0;color:#a62b2b;padding:10px;border-radius:10px;margin-bottom:12px">{html.escape(error)}</div>' if error else ""
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الدخول - صيدلية عز الصحة</title><style>body{{font-family:Tahoma,Arial;margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f7fb}}.card{{width:min(420px,92vw);background:#fff;padding:30px;border-radius:20px;box-shadow:0 15px 50px #0002}}h1{{text-align:center}}label{{display:block;margin:12px 0 6px;font-weight:bold}}input{{width:100%;padding:12px;border:1px solid #ccd7e2;border-radius:10px;font-size:16px}}button{{width:100%;margin-top:18px;padding:12px;border:0;border-radius:10px;background:#1e6f95;color:white;font-size:16px;font-weight:bold}}</style></head><body><div class="card"><img src="/static/logo-mark.png" style="width:72px;display:block;margin:0 auto 15px"><h1>صيدلية عز الصحة</h1><p style="text-align:center">تسجيل الدخول إلى نظام متابعة الطلبات</p>{err}<form method="post"><label>اسم المستخدم</label><input name="username" required autofocus><label>كلمة المرور</label><input type="password" name="password" required><button>دخول</button></form></div></body></html>'''

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    now = time.time(); q = _attempts[ip]
    while q and now - q[0] > _WINDOW: q.popleft()
    if request.method == "GET":
        if session.get("authenticated"): return redirect(url_for("index"))
        return login_page()
    if len(q) >= _MAX_ATTEMPTS: return login_page("تم تجاوز عدد المحاولات المسموح بها. حاول لاحقًا."), 429
    q.append(now)
    if request.form.get("username", "").strip() == AUTH_USERNAME and verify_password(request.form.get("password", "")):
        session.clear(); session.permanent = True; session["authenticated"] = True; session["username"] = AUTH_USERNAME
        return redirect(url_for("index"))
    return login_page("اسم المستخدم أو كلمة المرور غير صحيحة."), 401

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear(); return redirect(url_for("login"))

@app.before_request
def require_auth():
    path = request.path
    if path in ("/login", "/logout") or path.startswith("/static/"): return None
    if session.get("authenticated"): return None
    if path.startswith("/api/"):
        return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
    return redirect(url_for("login", next=request.full_path))

@app.after_request
def auth_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response
