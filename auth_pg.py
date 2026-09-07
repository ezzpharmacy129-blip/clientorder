# -*- coding: utf-8 -*-
"""PostgreSQL-native authentication, users and audit for Render production."""
import os
import sqlite3
import secrets
import hashlib
import hmac
import base64
import uuid
import html
from datetime import datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo
from flask import request, session, redirect, jsonify, url_for, render_template_string
from csrf_protection import install_csrf
from login_rate_limit import is_limited as login_rate_limited, record_failure as record_login_failure, clear as clear_login_attempts

TZ = ZoneInfo("Asia/Riyadh")

def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

def hash_password(password):
    password = str(password or "")
    if not password:
        raise ValueError("كلمة المرور مطلوبة")
    iterations = 310000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return f"pbkdf2_sha256${iterations}${enc(salt)}${enc(digest)}"

def verify_password(password, encoded):
    try:
        method, it, salt, digest = str(encoded).split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        dec = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", str(password).encode(), dec(salt), int(it))
        return hmac.compare_digest(actual, dec(digest))
    except Exception:
        return False

def install_auth(app, db):
    if getattr(app, "_ezz_auth_installed", False):
        return
    if getattr(db.__class__, "__module__", "") != "cloud_db":
        raise RuntimeError("auth_pg requires the PostgreSQL/CloudDB backend")

    secret = os.environ.get("SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("SECRET_KEY is required in production")
    app._ezz_auth_installed = True
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    install_csrf(app)

    root = os.path.abspath(getattr(db, "SHARED_ROOT", os.path.join(os.path.expanduser("~"), ".ezz_pharmacy_fresh")))
    os.makedirs(root, exist_ok=True)
    legacy_users_db = os.path.join(root, "users.sqlite3")

    def ensure_pg_users():
        with db._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users(
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','employee')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TEXT NOT NULL,
                last_login TEXT,
                session_version INTEGER NOT NULL DEFAULT 1
            )""")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TEXT")
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 1")
            au = os.environ.get("ADMIN_USERNAME", "").strip()
            ap = os.environ.get("ADMIN_PASSWORD", "")
            if au and ap:
                conn.execute("""INSERT INTO users(user_id,username,name,password_hash,role,active,created_at,last_login)
                    VALUES(%s,%s,%s,%s,'admin',TRUE,%s,NULL)
                    ON CONFLICT(username) DO UPDATE SET
                        name=EXCLUDED.name,
                        password_hash=EXCLUDED.password_hash,
                        role='admin',
                        active=TRUE""", (str(uuid.uuid4()), au, au, hash_password(ap), now_str()))

    def migrate_legacy_sqlite():
        if not os.path.exists(legacy_users_db):
            return
        try:
            with sqlite3.connect(legacy_users_db, timeout=10) as old:
                old.row_factory = sqlite3.Row
                try:
                    rows = old.execute("SELECT user_id,username,name,password_hash,role,active,created_at,last_login FROM users").fetchall()
                except sqlite3.OperationalError:
                    rows = old.execute("SELECT user_id,username,name,password_hash,role,active,created_at FROM users").fetchall()
            with db._connect() as conn:
                for r in rows:
                    conn.execute("""INSERT INTO users(user_id,username,name,password_hash,role,active,created_at,last_login)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(username) DO NOTHING""", (
                        str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), bool(r[5]), str(r[6]), r[7] if len(r) > 7 else None
                    ))
        except Exception:
            pass

    ensure_pg_users()
    migrate_legacy_sqlite()

    def get_user(user_id=None, username=None):
        if not user_id and not username:
            return None
        col = "user_id" if user_id else "username"
        value = user_id or username
        with db._connect() as conn:
            row = conn.execute(f"SELECT user_id,username,name,password_hash,role,active,created_at,last_login,COALESCE(session_version,1) AS session_version FROM users WHERE {col}=%s", (value,)).fetchone()
        return dict(row) if row else None

    def current_user():
        uid = str(session.get("user_id") or "").strip()
        if not uid:
            return None
        user = get_user(user_id=uid)
        if not user or not bool(user.get("active")):
            session.clear()
            return None
        stored_version = int(user.get("session_version") or 1)
        session_version = session.get("session_version")
        try:
            session_version = int(session_version)
        except (TypeError, ValueError):
            session_version = None
        if session_version != stored_version:
            session.clear()
            return None
        return user

    def audit(order_id="", action="", old_status="", new_status="", note="", actor=None):
        actor = actor or current_user()
        username = (actor or {}).get("name") or "غير مسجل"
        try:
            with db._connect() as conn:
                db._log(conn, str(order_id or ""), str(action or ""), str(old_status or ""), str(new_status or ""), str(note or ""), username)
        except Exception:
            pass

    def bump_session_version(user_id):
        with db._connect() as conn:
            row = conn.execute(
                "UPDATE users SET session_version=COALESCE(session_version,1)+1 WHERE user_id=%s RETURNING session_version",
                (user_id,),
            ).fetchone()
            return int(row["session_version"]) if row else None

    def set_last_login(user_id):
        try:
            with db._connect() as conn:
                conn.execute("UPDATE users SET last_login=%s WHERE user_id=%s", (now_str(), user_id))
        except Exception:
            pass

    def list_users():
        with db._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT user_id,username,name,role,active,created_at,last_login FROM users ORDER BY created_at DESC").fetchall()]

    def create_user(name, username, password, role):
        uid = str(uuid.uuid4())
        with db._connect() as conn:
            conn.execute("INSERT INTO users(user_id,username,name,password_hash,role,active,created_at,last_login) VALUES(%s,%s,%s,%s,%s,TRUE,%s,NULL)", (uid, username, name, hash_password(password), role, now_str()))
        return uid

    def toggle_user(uid, actor_uid):
        with db._connect() as conn:
            row = conn.execute("SELECT username,active FROM users WHERE user_id=%s", (uid,)).fetchone()
            if not row:
                return None, "المستخدم غير موجود"
            if uid == actor_uid and bool(row["active"]):
                return None, "لا يمكنك تعطيل حسابك الحالي"
            new = not bool(row["active"])
            conn.execute(
                "UPDATE users SET active=%s, session_version=COALESCE(session_version,1)+1 WHERE user_id=%s",
                (new, uid),
            )
            return new, None

    def change_password(uid, password):
        with db._connect() as conn:
            row = conn.execute("SELECT username FROM users WHERE user_id=%s", (uid,)).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE users SET password_hash=%s, session_version=COALESCE(session_version,1)+1 WHERE user_id=%s",
                (hash_password(password), uid),
            )
            return row["username"]

    app.extensions["ezz_auth"] = {
        "current_user": current_user,
        "get_user": get_user,
        "audit": audit,
        "hash_password": hash_password,
        "verify_password": verify_password,
        "is_cloud": True,
        "list_users": list_users,
        "create_user": create_user,
        "toggle_user": toggle_user,
        "change_password": change_password,
    }
    db._auth_user_provider = current_user

    @app.before_request
    def require_auth():
        p = request.path
        if p in ("/login", "/logout", "/health") or p.startswith("/static/"):
            return None
        if current_user():
            return None
        if p.startswith("/api/") or p.startswith("/uploads/"):
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        return redirect(url_for("ezz_login", next=request.full_path))

    @app.route("/login", methods=["GET", "POST"], endpoint="ezz_login")
    def login():
        if request.method == "GET":
            return redirect(url_for("index")) if current_user() else login_page()

        username = str(request.form.get("username") or "").strip()
        password = str(request.form.get("password") or "")
        remote_addr = request.remote_addr or "unknown"

        limited, retry_after = login_rate_limited(remote_addr, username)
        if limited:
            response = jsonify({
                "error": "تم تجاوز عدد محاولات تسجيل الدخول. حاول مرة أخرى لاحقًا.",
                "code": "login_rate_limited",
                "retry_after": retry_after,
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            audit(
                action="Rate Limited Login",
                note=f"تم حظر محاولات الدخول مؤقتًا للمستخدم: {username or 'غير معروف'}",
                actor={"name": username or "غير معروف"},
            )
            return response

        user = get_user(username=username)
        if user and bool(user.get("active")) and verify_password(password, user.get("password_hash", "")):
            clear_login_attempts(remote_addr, username)
            new_version = bump_session_version(user["user_id"])
            session.clear()
            session.permanent = True
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["session_version"] = new_version
            set_last_login(user["user_id"])
            audit(action="Login", note="تسجيل دخول ناجح", actor=user)
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt if str(nxt).startswith("/") else url_for("index"))

        count, retry_after = record_login_failure(remote_addr, username)
        audit(
            action="Failed Login",
            note=f"محاولة دخول فاشلة باسم المستخدم: {username or 'غير معروف'}",
            actor={"name": username or "غير معروف"},
        )
        if count >= 5:
            response = jsonify({
                "error": "تم تجاوز عدد محاولات تسجيل الدخول. حاول مرة أخرى لاحقًا.",
                "code": "login_rate_limited",
                "retry_after": retry_after,
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(max(1, retry_after))
            return response

        return login_page("اسم المستخدم أو كلمة المرور غير صحيحة."), 401

    @app.route("/logout", methods=["GET", "POST"], endpoint="ezz_logout")
    def logout():
        user = current_user()
        if user:
            audit(action="Logout", note="تسجيل الخروج", actor=user)
            try:
                bump_session_version(user["user_id"])
            except Exception:
                pass
        session.clear()
        response = redirect(url_for("ezz_login"))
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/auth/csrf")
    def auth_csrf():
        auth = app.extensions.get("ezz_csrf") or {}
        provider = auth.get("token")
        if not callable(provider):
            return jsonify({"error": "رمز الحماية غير متاح"}), 500
        return jsonify({"csrf_token": provider()})

    @app.get("/api/auth/me")
    def auth_me():
        user = current_user()
        return jsonify({"authenticated": bool(user), "user": ({"user_id": user["user_id"], "username": user["username"], "name": user["name"], "role": user["role"]} if user else None)})

    @app.get("/api/admin/users")
    def api_list_users():
        return jsonify({"users": list_users()})

    @app.post("/api/admin/users")
    def api_add_user():
        d = request.get_json(silent=True) or {}
        name = str(d.get("name") or "").strip(); username = str(d.get("username") or "").strip(); password = str(d.get("password") or ""); role = str(d.get("role") or "employee")
        if not name or len(username) < 3 or len(password) < 8:
            return jsonify({"error": "الاسم مطلوب واسم المستخدم 3 أحرف على الأقل وكلمة المرور 8 أحرف على الأقل"}), 400
        if role not in ("admin", "employee"):
            return jsonify({"error": "الدور غير صحيح"}), 400
        try:
            uid = create_user(name, username, password, role)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "unique" in msg:
                return jsonify({"error": "اسم المستخدم موجود بالفعل"}), 409
            return jsonify({"error": "تعذر إنشاء المستخدم"}), 500
        audit(action="Create User", note=f"إنشاء المستخدم {username}")
        return jsonify({"success": True, "user_id": uid}), 201

    @app.post("/api/admin/users/<uid>/toggle")
    def api_toggle_user(uid):
        actor = current_user(); active, error = toggle_user(uid, actor["user_id"])
        if error:
            return jsonify({"error": error}), 400 if "تعطيل" in error else 404
        target = get_user(user_id=uid)
        audit(action="Toggle User", note=f"تغيير حالة المستخدم {target['username']} إلى {'نشط' if active else 'معطل'}")
        return jsonify({"success": True, "active": bool(active)})

    @app.post("/api/admin/users/<uid>/password")
    def api_change_password(uid):
        password = str((request.get_json(silent=True) or {}).get("password") or "")
        if len(password) < 8:
            return jsonify({"error": "كلمة المرور يجب ألا تقل عن 8 أحرف"}), 400
        username = change_password(uid, password)
        if not username:
            return jsonify({"error": "المستخدم غير موجود"}), 404
        audit(action="Change Password", note=f"تغيير كلمة مرور المستخدم {username}")
        return jsonify({"success": True})

    @app.get("/admin")
    def admin_dashboard():
        rows = list_users(); active = sum(1 for r in rows if bool(r.get("active")))
        return admin_html("لوحة الإدارة", f"<div class='admin-card'><strong>{active}</strong><span>المستخدمون النشطون</span></div><div class='admin-actions'><a href='/admin/users'>إدارة المستخدمين</a><a href='/admin/audit'>Audit Log</a><a href='/'>العودة للنظام</a></div>")

    @app.get("/admin/users")
    @admin_only
    def admin_users():
        rows = list_users()
        body = "<div class='admin-actions'><a href='/admin'>لوحة الإدارة</a><a href='/admin/audit'>Audit Log</a><a href='/'>العودة للنظام</a></div><div class='panel'><h2>إضافة مستخدم</h2><form id='add-user' class='form-grid'><input name='name' placeholder='الاسم' required><input name='username' placeholder='Username' required><input name='password' type='password' placeholder='كلمة المرور' minlength='8' required><select name='role'><option value='employee'>employee</option><option value='admin'>admin</option></select><button>إضافة مستخدم</button></form></div><div class='panel'><h2>المستخدمون</h2><table><tr><th>الاسم</th><th>Username</th><th>الدور</th><th>الحالة</th><th>آخر دخول</th><th>الإجراءات</th></tr>"
        for r in rows:
            body += f"<tr><td>{esc(r['name'])}</td><td>{esc(r['username'])}</td><td>{esc(r['role'])}</td><td>{'نشط' if r['active'] else 'معطل'}</td><td>{esc(r.get('last_login') or '—')}</td><td><button onclick=\"toggleUser('{r['user_id']}')\">{'تعطيل' if r['active'] else 'تفعيل'}</button> <button onclick=\"changePassword('{r['user_id']}')\">تغيير كلمة المرور</button></td></tr>"
        body += "</table></div><script src='/static/csrf-client.js'></script><script>async function j(u,b){let r=await ezzCsrf.fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});let d=await r.json();if(!r.ok)throw Error(d.error||'حدث خطأ');return d}document.getElementById('add-user').onsubmit=async e=>{e.preventDefault();let f=e.target;try{await j('/api/admin/users',{name:f.name.value,username:f.username.value,password:f.password.value,role:f.role.value});location.reload()}catch(x){alert(x.message)}};async function toggleUser(id){try{await j('/api/admin/users/'+id+'/toggle')}catch(x){alert(x.message)}location.reload()}async function changePassword(id){let p=prompt('كلمة المرور الجديدة');if(!p)return;try{await j('/api/admin/users/'+id+'/password',{password:p});alert('تم تغيير كلمة المرور')}catch(x){alert(x.message)}}</script>"
        return admin_html("إدارة المستخدمين", body)

    @app.get("/admin/audit")
    @admin_only
    def admin_audit():
        try:
            rows = db.get_activity_log(None)
        except Exception:
            rows = []
        body = "<div class='admin-actions'><a href='/admin'>لوحة الإدارة</a><a href='/admin/users'>إدارة المستخدمين</a><a href='/'>العودة للنظام</a></div><div class='panel'><h2>Audit Log</h2><table><tr><th>التاريخ</th><th>المستخدم</th><th>العملية</th><th>الطلب</th><th>التفاصيل</th></tr>"
        for r in rows[:1000]:
            detail = r.get("Note", "")
            if r.get("Old_Status") or r.get("New_Status"):
                detail += (" — " if detail else "") + f"{r.get('Old_Status') or '—'} ← {r.get('New_Status') or '—'}"
            body += f"<tr><td>{esc(r.get('Created_At'))}</td><td>{esc(r.get('User'))}</td><td>{esc(r.get('Action'))}</td><td>{esc(r.get('Order_ID'))}</td><td>{esc(detail)}</td></tr>"
        return admin_html("Audit Log", body + "</table></div>")

    @app.before_request
    def admin_destructive_guard():
        if request.path in ("/api/data/reset", "/api/backups/restore"):
            user = current_user()
            if not user:
                return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
            if user.get("role") != "admin":
                return jsonify({"error": "غير مصرح لك بهذا الإجراء"}), 403

    @app.after_request
    def auth_headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

def esc(v):
    return html.escape(str(v or ""), quote=True)

def login_page(error=""):
    e = f"<div class='error'>{esc(error)}</div>" if error else ""
    return render_template_string("""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='csrf-token' content='{{ csrf_token() }}'><title>تسجيل الدخول - صيدلية عز الصحة</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5fafb;font-family:Tahoma,Arial,sans-serif;color:#17324d}.card{width:min(420px,92vw);background:#fff;border:1px solid #d9e7ea;border-radius:22px;padding:30px;box-shadow:0 18px 60px rgba(18,63,122,.14)}h1{text-align:center;color:#123f7a;font-size:23px}.field{margin-bottom:14px}.field label{display:block;font-weight:700;margin-bottom:7px}.field input{width:100%;padding:13px;box-sizing:border-box;border:1px solid #d9e7ea;border-radius:11px;font-size:16px}.submit{width:100%;border:0;border-radius:11px;padding:13px;background:#0b8f9b;color:#fff;font-weight:800;font-size:16px}.error{background:#fff0f0;color:#a62b2b;border:1px solid #f0c8c8;padding:10px;border-radius:10px;margin-bottom:12px}</style></head><body><div class='card'><h1>صيدلية عز الصحة</h1><p style='text-align:center'>تسجيل الدخول إلى نظام متابعة الطلبات</p>__ERROR__<form method='post'><input type='hidden' name='csrf_token' value='{{ csrf_token() }}'><div class='field'><label>اسم المستخدم</label><input name='username' autocomplete='username' required autofocus></div><div class='field'><label>كلمة المرور</label><input type='password' name='password' autocomplete='current-password' required></div><button class='submit'>تسجيل الدخول</button></form></div></body></html>""".replace("__ERROR__", e))

def admin_html(title, body):
    return render_template_string("""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='csrf-token' content='{{ csrf_token() }}'><title>{{title}} - صيدلية عز الصحة</title><style>:root{--primary:#0b8f9b;--navy:#123f7a;--border:#d9e7ea;--bg:#f5fafb}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#17324d;font-family:Tahoma,Arial,sans-serif}.wrap{max-width:1200px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.top a,.admin-actions a{display:inline-block;text-decoration:none;color:var(--navy);background:#fff;border:1px solid var(--border);padding:9px 12px;border-radius:9px;font-weight:700}.admin-card,.panel{background:#fff;border:1px solid var(--border);border-radius:14px;padding:18px;margin-bottom:16px}.admin-card strong{display:block;font-size:30px;color:var(--navy)}.admin-card span{color:#6c7f8a;font-size:13px}.admin-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 18px}.form-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.form-grid input,.form-grid select{padding:10px;border:1px solid var(--border);border-radius:9px}.form-grid button{border:0;border-radius:9px;background:var(--primary);color:#fff;font-weight:700;padding:10px 14px}.panel{overflow:auto}table{width:100%;border-collapse:collapse;min-width:760px}th,td{border-bottom:1px solid var(--border);padding:10px;text-align:right}th{background:#f4fafb;color:var(--navy);font-size:12px}.panel button{border:1px solid var(--primary);background:#fff;color:var(--navy);border-radius:8px;padding:6px 9px}.panel button:hover{background:#eaf8f9}@media(max-width:760px){.form-grid{grid-template-columns:1fr}}</style></head><body><div class='wrap'><div class='top'><h1>{{title}}</h1><a href='/logout'>🚪 تسجيل الخروج</a></div>__BODY__</div></body></html>""".replace("__BODY__", body), title=title)
