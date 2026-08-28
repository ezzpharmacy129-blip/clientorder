# -*- coding: utf-8 -*-
import os
import secrets
import hashlib
import hmac
import uuid
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo
from flask import request, session, redirect, jsonify, url_for, render_template_string

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
    return "pbkdf2_sha256${}${}${}".format(iterations, _b64(salt), _b64(digest))


def _b64(value):
    import base64
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def verify_password(password, encoded):
    try:
        import base64
        method, iterations, salt, digest = str(encoded).split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        salt_b = base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4))
        expected = base64.urlsafe_b64decode(digest + "=" * (-len(digest) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt_b, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def install_auth(app, db):
    if getattr(app, "_ezz_auth_installed", False):
        return
    app._ezz_auth_installed = True
    secret = os.environ.get("SECRET_KEY", "").strip()
    if not secret:
        # Development fallback only. Render/production must provide SECRET_KEY.
        secret = secrets.token_hex(32)
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER") or os.environ.get("PRODUCTION")),
        PERMANENT_SESSION_LIFETIME=12 * 60 * 60,
    )

    if not hasattr(db, "_connect"):
        # The deployed application uses PostgreSQL. Keep the existing local Excel backend untouched.
        raise RuntimeError("Authentication requires the PostgreSQL cloud backend")

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
                    conn.execute(
                        "INSERT INTO users(user_id,username,name,password_hash,role,active,created_at) VALUES (%s,%s,%s,%s,'admin',TRUE,%s)",
                        (str(uuid.uuid4()), admin_username, admin_username, hash_password(admin_password), now_str())
                    )

    def get_user(user_id=None, username=None):
        with db._connect() as conn:
            if user_id:
                row = conn.execute("SELECT user_id,username,name,password_hash,role,active,created_at FROM users WHERE user_id=%s", (user_id,)).fetchone()
            elif username:
                row = conn.execute("SELECT user_id,username,name,password_hash,role,active,created_at FROM users WHERE username=%s", (username,)).fetchone()
            else:
                row = None
        return dict(row) if row else None

    def current_user():
        user = get_user(user_id=session.get("user_id")) if session.get("user_id") else None
        if not user or not user["active"]:
            if session.get("user_id"):
                session.clear()
            return None
        return user

    def audit(order_id="", action="", old_status="", new_status="", note="", actor=None):
        actor = actor or current_user()
        username = actor["name"] if actor else "غير مسجل"
        with db._connect() as conn:
            conn.execute(
                "INSERT INTO activity_log(log_id,order_id,action,old_status,new_status,note,created_at,user_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                ("AUTH-" + uuid.uuid4().hex[:12], str(order_id or ""), action, old_status or "", new_status or "", note or "", now_str(), username)
            )

    ensure_users()
    app.extensions["ezz_auth"] = {"current_user": current_user, "get_user": get_user, "audit": audit, "hash_password": hash_password, "verify_password": verify_password}
    db._auth_user_provider = current_user

    # Make all existing DB activity records use the real logged-in user's name when routes omit user explicitly.
    if hasattr(db, "_log"):
        original_log = db._log
        def cloud_log(conn, order_id, action, old_status, new_status, note, user="موظف"):
            u = current_user()
            return original_log(conn, order_id, action, old_status, new_status, note, u["name"] if u and user == "موظف" else user)
        db._log = cloud_log
    if hasattr(db, "_append_log"):
        original_append = db._append_log
        def excel_log(ws, order_id, action, old_status, new_status, note, user="موظف"):
            u = current_user()
            return original_append(ws, order_id, action, old_status, new_status, note, u["name"] if u and user == "موظف" else user)
        db._append_log = excel_log

    def require_auth():
        path = request.path
        if path in ("/login", "/logout", "/health") or path.startswith("/static/"):
            return None
        if current_user():
            return None
        if path.startswith("/api/") or path.startswith("/uploads/"):
            return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
        return redirect(url_for("ezz_login", next=request.full_path))
    app.before_request(require_auth)

    def login_page(error=""):
        return render_template_string("""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>تسجيل الدخول - صيدلية عز الصحة</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5fafb;font-family:Tahoma,Arial,sans-serif;color:#17324d}.card{width:min(420px,92vw);background:#fff;border:1px solid #d9e7ea;border-radius:22px;padding:30px;box-shadow:0 18px 60px rgba(18,63,122,.14)}.logo{width:76px;height:76px;object-fit:contain;display:block;margin:0 auto 16px}.card h1{text-align:center;margin:0 0 6px;color:#123f7a;font-size:23px}.card p{text-align:center;color:#6c7f8a;margin:0 0 22px}.error{background:#fff0f0;color:#a62b2b;border:1px solid #f0c8c8;padding:10px;border-radius:10px;margin-bottom:12px}.field{margin-bottom:14px}.field label{display:block;font-weight:700;margin-bottom:7px}.field input{width:100%;padding:13px;box-sizing:border-box;border:1px solid #d9e7ea;border-radius:11px;font-size:16px}.submit{width:100%;border:0;border-radius:11px;padding:13px;background:#0b8f9b;color:#fff;font-weight:800;font-size:16px;cursor:pointer}.small{text-align:center;color:#94a0ac;font-size:12px;margin-top:16px}</style></head><body><div class='card'><img class='logo' src='/static/logo-mark.png' alt='شعار صيدلية عز الصحة'><h1>صيدلية عز الصحة</h1><p>تسجيل الدخول إلى نظام متابعة الطلبات</p>{error}<form method='post'><div class='field'><label>اسم المستخدم</label><input name='username' autocomplete='username' required autofocus></div><div class='field'><label>كلمة المرور</label><input type='password' name='password' autocomplete='current-password' required></div><button class='submit'>تسجيل الدخول</button></form><div class='small'>الوصول إلى النظام مخصص للمستخدمين المصرح لهم.</div></div></body></html>""".replace("{error}", f"<div class='error'>{error}</div>" if error else ""))

    @app.route("/login", methods=["GET", "POST"], endpoint="ezz_login")
    def login():
        if request.method == "GET":
            if current_user():
                return redirect(url_for("index"))
            return login_page()
        username = str(request.form.get("username") or "").strip()
        password = str(request.form.get("password") or "")
        user = get_user(username=username)
        if user and user["active"] and verify_password(password, user["password_hash"]):
            session.clear()
            session.permanent = True
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            audit(action="Login", note="تسجيل دخول ناجح", actor=user)
            nxt = request.args.get("next") or url_for("index")
            if not str(nxt).startswith("/"):
                nxt = url_for("index")
            return redirect(nxt)
        # Failed login has no authenticated user, so store the attempted username only as the audit actor.
        audit(action="Failed Login", note=f"محاولة دخول فاشلة باسم المستخدم: {username or 'غير معروف'}", actor={"name": username or "غير معروف"})
        return login_page("اسم المستخدم أو كلمة المرور غير صحيحة."), 401

    @app.route("/logout", methods=["GET", "POST"], endpoint="ezz_logout")
    def logout():
        user = current_user()
        if user:
            audit(action="Logout", note="تسجيل الخروج", actor=user)
        session.clear()
        response = redirect(url_for("ezz_login"))
        response.headers["Cache-Control"] = "no-store"
        return response

    def admin_only(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error":"تسجيل الدخول مطلوب","authenticated":False}), 401
            if user["role"] != "admin":
                return jsonify({"error":"غير مصرح لك بهذا الإجراء"}), 403
            return fn(*args, **kwargs)
        return wrapped

    @app.get("/api/auth/me")
    def auth_me():
        u = current_user()
        return jsonify({"authenticated":bool(u), "user":({"user_id":u["user_id"],"username":u["username"],"name":u["name"],"role":u["role"]} if u else None)})

    @app.get("/admin")
    @admin_only
    def admin_dashboard():
        with db._connect() as conn:
            users_count = conn.execute("SELECT COUNT(*) AS c FROM users WHERE active=TRUE").fetchone()["c"]
        return admin_html("لوحة الإدارة", f"<div class='admin-grid'><div class='admin-card'><strong>{users_count}</strong><span>المستخدمون النشطون</span></div></div><div class='admin-actions'><a href='/admin/users'>إدارة المستخدمين</a><a href='/admin/audit'>Audit Log</a><a href='/'>العودة للنظام</a></div>")

    @app.get("/admin/users")
    @admin_only
    def admin_users_page():
        with db._connect() as conn:
            rows = conn.execute("SELECT user_id,username,name,role,active,created_at FROM users ORDER BY created_at DESC").fetchall()
        body = "<div class='admin-actions'><a href='/admin'>لوحة الإدارة</a><a href='/admin/audit'>Audit Log</a><a href='/'>العودة للنظام</a></div><div class='panel'><h2>إضافة مستخدم</h2><form id='add-user' class='form-grid'><input name='name' placeholder='الاسم' required><input name='username' placeholder='Username' required><input name='password' type='password' placeholder='كلمة المرور' required><select name='role'><option value='employee'>employee</option><option value='admin'>admin</option></select><button>إضافة مستخدم</button></form></div><div class='panel'><h2>المستخدمون</h2><table><tr><th>الاسم</th><th>Username</th><th>الدور</th><th>الحالة</th><th>الإجراءات</th></tr>"
        for r in rows:
            state = "نشط" if r["active"] else "معطل"
            toggle = "تعطيل" if r["active"] else "تفعيل"
            body += f"<tr><td>{_esc(r['name'])}</td><td>{_esc(r['username'])}</td><td>{_esc(r['role'])}</td><td>{state}</td><td><button class='action' onclick=\"toggleUser('{r['user_id']}')\">{toggle}</button> <button class='action' onclick=\"changePassword('{r['user_id']}')\">تغيير كلمة المرور</button></td></tr>"
        body += "</table></div><script>async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});const d=await r.json();if(!r.ok)throw Error(d.error||'حدث خطأ');return d}document.getElementById('add-user').onsubmit=async e=>{e.preventDefault();const f=e.target;try{await post('/api/admin/users',{name:f.name.value,username:f.username.value,password:f.password.value,role:f.role.value});location.reload()}catch(x){alert(x.message)}};async function toggleUser(id){try{await post('/api/admin/users/'+id+'/toggle');location.reload()}catch(x){alert(x.message)}}async function changePassword(id){const p=prompt('أدخل كلمة المرور الجديدة');if(!p)return;try{await post('/api/admin/users/'+id+'/password',{password:p});alert('تم تغيير كلمة المرور')}catch(x){alert(x.message)}}</script>"
        return admin_html("إدارة المستخدمين", body)

    @app.get("/admin/audit")
    @admin_only
    def admin_audit_page():
        with db._connect() as conn:
            rows = conn.execute("SELECT created_at,user_name,action,order_id,note,old_status,new_status FROM activity_log ORDER BY created_at DESC LIMIT 1000").fetchall()
        body = "<div class='admin-actions'><a href='/admin'>لوحة الإدارة</a><a href='/admin/users'>إدارة المستخدمين</a><a href='/'>العودة للنظام</a></div><div class='panel'><h2>Audit Log</h2><table><tr><th>التاريخ</th><th>المستخدم</th><th>العملية</th><th>الطلب</th><th>التفاصيل</th></tr>"
        for r in rows:
            detail = str(r["note"] or "")
            if r["old_status"] or r["new_status"]:
                detail += (" — " if detail else "") + f"{r['old_status'] or '—'} ← {r['new_status'] or '—'}"
            body += f"<tr><td>{_esc(r['created_at'])}</td><td>{_esc(r['user_name'])}</td><td>{_esc(r['action'])}</td><td>{_esc(r['order_id'])}</td><td>{_esc(detail)}</td></tr>"
        body += "</table></div>"
        return admin_html("Audit Log", body)

    @app.post("/api/admin/users")
    @admin_only
    def api_add_user():
        data = request.get_json(silent=True) or {}
        name, username, password, role = [str(data.get(k) or "").strip() for k in ("name","username","password","role")]
        if not name or not username or not password:
            return jsonify({"error":"الاسم واسم المستخدم وكلمة المرور مطلوبة"}), 400
        if role not in ("admin","employee"):
            return jsonify({"error":"الدور غير صحيح"}), 400
        with db._connect() as conn:
            if conn.execute("SELECT 1 FROM users WHERE username=%s", (username,)).fetchone():
                return jsonify({"error":"اسم المستخدم موجود بالفعل"}), 409
            uid = str(uuid.uuid4())
            conn.execute("INSERT INTO users(user_id,username,name,password_hash,role,active,created_at) VALUES (%s,%s,%s,%s,%s,TRUE,%s)", (uid,username,name,hash_password(password),role,now_str()))
        audit(action="Create User", note=f"إنشاء المستخدم {username}")
        return jsonify({"success":True}), 201

    @app.post("/api/admin/users/<user_id>/toggle")
    @admin_only
    def api_toggle_user(user_id):
        actor = current_user()
        with db._connect() as conn:
            row = conn.execute("SELECT username,active FROM users WHERE user_id=%s", (user_id,)).fetchone()
            if not row:
                return jsonify({"error":"المستخدم غير موجود"}), 404
            if user_id == actor["user_id"] and row["active"]:
                return jsonify({"error":"لا يمكنك تعطيل حسابك الحالي"}), 400
            conn.execute("UPDATE users SET active=NOT active WHERE user_id=%s", (user_id,))
            new_state = conn.execute("SELECT active FROM users WHERE user_id=%s", (user_id,)).fetchone()["active"]
        audit(action="Toggle User", note=f"تغيير حالة المستخدم {row['username']} إلى {'نشط' if new_state else 'معطل'}")
        return jsonify({"success":True,"active":bool(new_state)})

    @app.post("/api/admin/users/<user_id>/password")
    @admin_only
    def api_change_password(user_id):
        password = str((request.get_json(silent=True) or {}).get("password") or "")
        if len(password) < 6:
            return jsonify({"error":"كلمة المرور يجب ألا تقل عن 6 أحرف"}), 400
        with db._connect() as conn:
            row = conn.execute("SELECT username FROM users WHERE user_id=%s", (user_id,)).fetchone()
            if not row:
                return jsonify({"error":"المستخدم غير موجود"}), 404
            conn.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (hash_password(password), user_id))
        audit(action="Change Password", note=f"تغيير كلمة مرور المستخدم {row['username']}")
        return jsonify({"success":True})

    @app.after_request
    def auth_security_headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/") and response.mimetype == "text/html" and request.path not in ("/login",):
            user = current_user()
            if user:
                marker = "</header>"
                bar = f"<div class='auth-user-bar'><span>المستخدم: <strong>{_esc(user['name'])}</strong></span>{'<a href=\"/admin\">الإدارة</a>' if user['role']=='admin' else ''}<a href='/logout'>تسجيل الخروج</a></div>"
                try:
                    html = response.get_data(as_text=True)
                    if marker in html and "auth-user-bar" not in html:
                        html = html.replace(marker, bar + marker, 1)
                        html = html.replace("</head>", "<style>.auth-user-bar{max-width:1280px;margin:0 auto;padding:7px 22px 10px;display:flex;align-items:center;justify-content:flex-start;gap:8px;flex-wrap:wrap;color:#6c7f8a;font-size:12px}.auth-user-bar a{color:#075b68;text-decoration:none;font-weight:800;background:#edf8f9;border:1px solid #d9e7ea;border-radius:8px;padding:6px 9px}.auth-user-bar a:last-child{background:#fff0ef;color:#a62b2b}@media(max-width:720px){.auth-user-bar{padding:6px 14px}.auth-user-bar a{padding:8px 10px}}</style></head>", 1)
                        response.set_data(html)
                except Exception:
                    pass
        return response


def _esc(value):
    import html
    return html.escape(str(value or ""), quote=True)


def admin_html(title, body):
    return render_template_string("""<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{{title}} - صيدلية عز الصحة</title><style>:root{--primary:#0b8f9b;--navy:#123f7a;--border:#d9e7ea;--bg:#f5fafb}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#17324d;font-family:Tahoma,Arial,sans-serif}.wrap{max-width:1200px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px}.top h1{margin:0;color:var(--navy);font-size:22px}.top a,.admin-actions a{display:inline-block;text-decoration:none;color:var(--navy);background:#fff;border:1px solid var(--border);padding:9px 12px;border-radius:9px;font-weight:700}.admin-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.admin-card,.panel{background:#fff;border:1px solid var(--border);border-radius:14px;padding:18px;margin-bottom:16px}.admin-card strong{display:block;font-size:30px;color:var(--navy)}.admin-card span{color:#6c7f8a;font-size:13px}.admin-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 18px}.form-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.form-grid input,.form-grid select{padding:10px;border:1px solid var(--border);border-radius:9px}.form-grid button{border:0;border-radius:9px;background:var(--primary);color:#fff;font-weight:700;padding:10px;cursor:pointer}table{width:100%;border-collapse:collapse;min-width:700px}th,td{padding:10px;border-bottom:1px solid var(--border);text-align:right;font-size:13px}th{background:#f4fafb;color:var(--navy)}.action{border:1px solid var(--border);background:#fff;border-radius:7px;padding:6px 8px;cursor:pointer}@media(max-width:760px){.form-grid{grid-template-columns:1fr}.wrap{padding:14px}.top h1{font-size:18px}}
</style></head><body><div class='wrap'><div class='top'><h1>{{title}}</h1><a href='/logout'>تسجيل الخروج</a></div>{{body|safe}}</div></body></html>""", title=title, body=body)
