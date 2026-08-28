# Experimental multi-user/admin layer for Ezz Pharmacy test deployment.
import os, sqlite3, secrets, functools
from flask import request, session, redirect, url_for, jsonify, render_template, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from app import app

app.secret_key = os.environ.get('ADMIN_SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE='Lax')
DB_FILE = os.environ.get('ADMIN_USERS_DB', '/tmp/ezz_admin_users.sqlite3')
PERMISSIONS = [
 ('view_orders','عرض الطلبات'),('add_order','إضافة طلب'),('edit_order','تعديل الطلب'),('delete_order','حذف الطلب'),
 ('change_status','تغيير حالة الطلب'),('undo_order','التراجع عن التغيير'),('whatsapp','إرسال WhatsApp'),('followups','إدارة المتابعات'),
 ('view_images','عرض الصور'),('manage_images','إدارة الصور'),('import_data','استيراد البيانات'),('backups','النسخ الاحتياطية'),
 ('restore_backup','استعادة النسخة الاحتياطية'),('delete_all_data','حذف جميع البيانات'),('settings','تعديل الإعدادات'),('manage_users','إدارة المستخدمين')]
ALL_KEYS = [x[0] for x in PERMISSIONS]


def conn():
    c=sqlite3.connect(DB_FILE); c.row_factory=sqlite3.Row; return c

def init_users():
    os.makedirs(os.path.dirname(DB_FILE) or '.', exist_ok=True)
    with conn() as c:
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, permissions TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('SELECT 1 FROM users LIMIT 1')
        if c.fetchone() is None:
            seed='ezzpharmacy579758700'
            c.execute('INSERT INTO users(username,password_hash,permissions) VALUES(?,?,?)', ('admin', generate_password_hash(seed), ','.join(ALL_KEYS)))
init_users()

def current_user():
    uid=session.get('uid')
    if not uid:return None
    with conn() as c:
        r=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone()
    return dict(r) if r else None

def user_permissions(u):
    return set((u.get('permissions') or '').split(','))

def needs(permission=None):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a,**kw):
            u=current_user()
            if not u:
                if request.path.startswith('/api/'): return jsonify({'error':'تسجيل الدخول مطلوب','authenticated':False}),401
                return redirect(url_for('admin_login', next=request.full_path))
            if permission and permission not in user_permissions(u):
                return jsonify({'error':'ليس لديك صلاحية تنفيذ هذا الإجراء','permission':permission}),403
            return fn(*a,**kw)
        return wrap
    return deco

@app.route('/login', methods=['GET','POST'])
def admin_login():
    if request.method=='GET':
        if current_user(): return redirect(url_for('index'))
        return render_template('login.html') if os.path.exists(os.path.join(app.template_folder or '', 'login.html')) else '<form method="post" style="max-width:400px;margin:15vh auto;font-family:Tahoma" dir="rtl"><h2>صيدلية عز الصحة</h2><input name="username" placeholder="اسم المستخدم" required style="width:100%;padding:10px"><input name="password" type="password" placeholder="كلمة المرور" required style="width:100%;padding:10px;margin-top:8px"><button style="width:100%;padding:10px;margin-top:8px">دخول</button></form>'
    with conn() as c: r=c.execute('SELECT * FROM users WHERE username=? AND active=1',(request.form.get('username','').strip(),)).fetchone()
    if r and check_password_hash(r['password_hash'], request.form.get('password','')):
        session.clear(); session.permanent=True; session['uid']=r['id']; session['username']=r['username']; return redirect(request.args.get('next') or url_for('index'))
    return ('<p dir="rtl">اسم المستخدم أو كلمة المرور غير صحيحة</p>',401)

@app.route('/logout')
def admin_logout(): session.clear(); return redirect(url_for('admin_login'))

@app.before_request
def global_guard():
    if request.path.startswith('/static/') or request.path in ('/login','/logout','/health'):
        return None
    if current_user(): return None
    if request.path.startswith('/api/'):
        return jsonify({'error':'تسجيل الدخول مطلوب','authenticated':False}),401
    return redirect(url_for('admin_login', next=request.full_path))

@app.after_request
def sec_headers(r):
    r.headers.setdefault('Cache-Control','no-store'); r.headers.setdefault('X-Content-Type-Options','nosniff'); r.headers.setdefault('X-Frame-Options','SAMEORIGIN'); return r

@app.route('/admin')
@needs('manage_users')
def admin_panel(): return render_template('admin.html', permissions=PERMISSIONS)

@app.get('/api/admin/me')
@needs()
def me():
    u=current_user(); return jsonify({'username':u['username'],'permissions':sorted(user_permissions(u))})

@app.get('/api/admin/users')
@needs('manage_users')
def list_users():
    with conn() as c: rows=c.execute('SELECT id,username,active,permissions,created_at FROM users ORDER BY username').fetchall()
    return jsonify({'users':[{'id':r['id'],'username':r['username'],'active':bool(r['active']),'permissions':[p for p in (r['permissions'] or '').split(',') if p],'created_at':r['created_at']} for r in rows]})

@app.post('/api/admin/users')
@needs('manage_users')
def add_user():
    d=request.get_json(silent=True) or {}; username=str(d.get('username') or '').strip(); password=str(d.get('password') or '')
    perms=[p for p in (d.get('permissions') or []) if p in ALL_KEYS]
    if len(username)<3 or len(password)<8:return jsonify({'error':'اسم المستخدم يجب أن يكون 3 أحرف على الأقل وكلمة المرور 8 أحرف على الأقل'}),400
    with conn() as c:
        try:c.execute('INSERT INTO users(username,password_hash,permissions) VALUES(?,?,?)',(username,generate_password_hash(password),','.join(sorted(set(perms)))))
        except sqlite3.IntegrityError:return jsonify({'error':'اسم المستخدم موجود بالفعل'}),409
    return jsonify({'success':True})

@app.put('/api/admin/users/<int:uid>')
@needs('manage_users')
def update_user(uid):
    d=request.get_json(silent=True) or {}; perms=[p for p in (d.get('permissions') or []) if p in ALL_KEYS]; active=1 if d.get('active',True) else 0; password=str(d.get('password') or '')
    with conn() as c:
        row=c.execute('SELECT username FROM users WHERE id=?',(uid,)).fetchone()
        if not row:return jsonify({'error':'المستخدم غير موجود'}),404
        if uid==session.get('uid') and not active:return jsonify({'error':'لا يمكن تعطيل المستخدم الذي تستخدمه الآن'}),400
        if password:
            if len(password)<8:return jsonify({'error':'كلمة المرور 8 أحرف على الأقل'}),400
            c.execute('UPDATE users SET password_hash=?,permissions=?,active=? WHERE id=?',(generate_password_hash(password),','.join(sorted(set(perms))),active,uid))
        else:c.execute('UPDATE users SET permissions=?,active=? WHERE id=?',(','.join(sorted(set(perms))),active,uid))
    return jsonify({'success':True})

@app.delete('/api/admin/users/<int:uid>')
@needs('manage_users')
def delete_user(uid):
    if uid==session.get('uid'):return jsonify({'error':'لا يمكن حذف المستخدم الذي تستخدمه الآن'}),400
    with conn() as c:c.execute('DELETE FROM users WHERE id=?',(uid,))
    return jsonify({'success':True})

# Server-side permission map for the existing application's destructive/mutating routes.
RULES=[
 ('GET','/api/orders','view_orders'),('POST','/api/orders','add_order'),('PUT','/api/orders/','edit_order'),('DELETE','/api/orders/','delete_order'),
 ('POST','/api/orders/','change_status'),('POST','/api/import-data','import_data'),('GET','/api/backups','backups'),('POST','/api/backups','backups'),
 ('POST','/api/backups/restore','restore_backup'),('POST','/api/data/reset','delete_all_data'),('PUT','/api/message-templates','settings'),('POST','/api/message-templates/reset','settings')]

def route_permission():
    p=request.path; m=request.method
    for rm,prefix,perm in RULES:
        if m==rm and p.startswith(prefix): return perm
    if '/items/' in p and p.endswith('/image'):
        return 'manage_images'
    if p.startswith('/api/whatsapp/'): return 'whatsapp'
    if p.startswith('/api/followups/'): return 'followups'
    return None

@app.before_request
def permission_guard():
    if request.path.startswith('/api/admin') or request.path in ('/login','/logout','/health') or request.path.startswith('/static/'):
        return None
    u=current_user()
    if not u:return None
    perm=route_permission()
    if perm and perm not in user_permissions(u):
        return jsonify({'error':'ليس لديك الصلاحية المطلوبة','permission':perm}),403
