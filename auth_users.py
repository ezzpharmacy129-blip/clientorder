# -*- coding: utf-8 -*-
import os
import secrets
import hashlib
import hmac
from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import jsonify, redirect, request, session, url_for

TZ = ZoneInfo("Asia/Riyadh")


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password):
    password = str(password or "")
    if not password:
        raise ValueError("كلمة المرور مطلوبة")
    iterations = 310000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(iterations, _b64(salt), _b64(digest))


def _b64(value):
    import base64
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def verify_password(password, encoded):
    try:
        method, iterations_s, salt_s, digest_s = str(encoded).split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        import base64
        salt = base64.urlsafe_b64decode(salt_s + "=" * (-len(salt_s) % 4))
        expected = base64.urlsafe_b64decode(digest_s + "=" * (-len(digest_s) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, int(iterations_s))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def init_auth(app, db):
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER") or os.environ.get("PRODUCTION")),
        PERMANENT_SESSION_LIFETIME=12 * 60 * 60,
    )

    def db_execute(sql, params=()):
        if hasattr(db, "_connect"):
            with db._connect() as conn:
                return conn.execute(sql, params).fetchall()
        raise RuntimeError("Users table requires cloud database")

    def ensure_users():
        with db._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','employee')),
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TEXT NOT NULL
                )
            """)
            admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
            admin_password = os.environ.get("ADMIN_PASSWORD", "")
            if admin_username and admin_password:
                row = conn.execute("SELECT user_id FROM users WHERE username=%s", (admin_username,)).fetchone()
                if not row:
                    import uuid
                    conn.execute(
                        "INSERT INTO users(user_id,username,name,password_hash,role,active,created_at) VALUES (%s,%s,%s,%s,'admin',TRUE,%s)",
                        (str(uuid.uuid4()), admin_username, admin_username, hash_password(admin_password), now_str())
                    )

    def current_user():
        uid = session.get("user_id")
        if not uid:
            return None
        rows = db_execute("SELECT user_id,username,name,role,active,created_at FROM users WHERE user_id=%s", (uid,))
        if not rows or not rows[0]["active"]:
            session.clear()
            return None
        return dict(rows[0])

    def audit(order_id, action, old_status="", new_status="", note=""):
        user = current_user()
        if not user:
            return
        with db._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log(log_id,order_id,action,old_status,new_status,note,created_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                ("AUTH-" + secrets.token_hex(8), str(order_id or ""), action, old_status or "", new_status or "", note or "", now_str(), user["name"])
            )

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user():
                if request.path.startswith("/api/"):
                    return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
                return redirect(url_for("login", next=request.full_path))
            return fn(*args, **kwargs)
        return wrapper

    def admin_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
                return redirect(url_for("login", next=request.full_path))
            if user["role"] != "admin":
                return jsonify({"error":"غير مصرح لك بهذا الإجراء"}), 403
            return fn(*args, **kwargs)
        return wrapper

    app.extensions["ezz_auth"] = {
        "ensure_users": ensure_users,
        "current_user": current_user,
        "audit": audit,
        "login_required": login_required,
        "admin_required": admin_required,
        "hash_password": hash_password,
        "verify_password": verify_password,
    }
    ensure_users()

    @app.context_processor
    def auth_context():
        return {"current_user": current_user()}

    return app.extensions["ezz_auth"]
