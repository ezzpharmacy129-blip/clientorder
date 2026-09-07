"""One-time production admin credential synchronizer.

Enabled only when ADMIN_PASSWORD_FORCE_SYNC=1. It changes only the password_hash,
role and active/session_version of the configured admin username; no business data
is touched. Disable the flag immediately after successful login verification.
"""
import os


def sync_admin_password(app, db):
    if os.environ.get("ADMIN_PASSWORD_FORCE_SYNC", "").strip() != "1":
        return False

    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD are required for forced admin password sync")

    auth = app.extensions.get("ezz_auth") or {}
    hasher = auth.get("hash_password")
    if not callable(hasher):
        raise RuntimeError("password hasher is not available")

    new_hash = hasher(password)
    with db._connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE username=%s",
            (username,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"admin user not found: {username}")
        conn.execute(
            """UPDATE users
               SET password_hash=%s,
                   role='admin',
                   active=TRUE,
                   session_version=COALESCE(session_version,1)+1
             WHERE username=%s""",
            (new_hash, username),
        )

    app.logger.info("AUTH_DIAG: forced_admin_password_sync=1 username=%s success=1", username)
    return True
