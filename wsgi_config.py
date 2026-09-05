"""Explicit production runtime wiring for Gunicorn.

Production uses CloudDB/PostgreSQL for all operational data and authentication.
Authentication is initialized explicitly here; no Flask constructor monkey-patching
or Excel/SQLite authentication is used in the cloud service.
"""

import os
import uuid


def _sync_admin_credentials(db):
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD are required for the production admin account")

    from auth_pg import hash_password, now_str
    with db._connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users(
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','employee')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TEXT NOT NULL,
                last_login TEXT
            )"""
        )
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TEXT")
        row = conn.execute("SELECT user_id FROM users WHERE username=%s", (username,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET name=%s,password_hash=%s,role='admin',active=TRUE WHERE username=%s",
                (username, hash_password(password), username),
            )
        else:
            conn.execute(
                """INSERT INTO users(user_id,username,name,password_hash,role,active,created_at,last_login)
                   VALUES(%s,%s,%s,%s,'admin',TRUE,%s,NULL)""",
                (str(uuid.uuid4()), username, username, hash_password(password), now_str()),
            )


def on_starting(server):
    from app import app
    from db import db

    if db.__class__.__module__ != "cloud_db":
        raise RuntimeError("Render production requires the CloudDB/PostgreSQL backend")

    from auth_pg import install_auth
    install_auth(app, db)
    _sync_admin_credentials(db)

    from login_rate_limit import install as install_login_rate_limit
    install_login_rate_limit(app)

    from auth_security_extensions import install_security_extensions
    install_security_extensions(app, db)

    from data_export import install_data_export
    install_data_export(app, db)

    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)

    from ai_assistant import install_ai
    install_ai(app)

    from ai_chat import install_ai_chat
    install_ai_chat(app, db)

    server.log.info("Ezz Pharmacy production runtime initialized with PostgreSQL auth")
