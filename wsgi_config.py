"""Explicit production runtime wiring for Gunicorn.

Authentication and production extensions are initialized through a normal
Gunicorn config hook. This removes the runtime's dependency on Flask
constructor monkey-patching for security-critical initialization.
"""

def _sync_admin_credentials(db):
    """Make Render ADMIN_* the authoritative credentials without touching orders."""
    import os
    import sqlite3
    import uuid
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        return
    root = os.path.abspath(getattr(db, "SHARED_ROOT", os.path.join(os.path.expanduser("~"), ".ezz_pharmacy_fresh")))
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "users.sqlite3")
    from auth_bootstrap import hash_password, now_str
    with sqlite3.connect(path, timeout=20) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','employee')),
            active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
        row = conn.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
        if row:
            conn.execute("UPDATE users SET name=?, password_hash=?, role='admin', active=1 WHERE username=?", (username, hash_password(password), username))
        else:
            conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), username, username, hash_password(password), "admin", 1, now_str()))

def on_starting(server):
    from app import app
    from db import db

    # The live application is Excel-backed; use the matching auth layer explicitly.
    from auth_bootstrap import install_auth
    install_auth(app, db)
    _sync_admin_credentials(db)

    from auth_security_extensions import install_security_extensions
    install_security_extensions(app, db)

    from data_export import install_data_export
    install_data_export(app, db)

    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)

    from admin_state_controls import install_admin_state_controls
    from pending_availability_fix import install_pending_availability_fix
    install_admin_state_controls(app, db)
    install_pending_availability_fix(db)

    server.log.info("Ezz Pharmacy explicit runtime wiring initialized")
    server.log.info("Ezz Pharmacy admin credentials synchronized from environment")
