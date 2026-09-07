"""Centralized PostgreSQL production security bootstrap.

The operation is intentionally idempotent because Gunicorn can call it after
Flask has already imported the application module.
"""


def install_production_security(app, db):
    """Install PostgreSQL authentication and authorization exactly once."""
    if db.__class__.__module__ != "cloud_db":
        return False

    if getattr(app, "_ezz_production_security_bootstrapped", False):
        return True

    from auth_pg import install_auth
    from authorization_policy import install_authorization
    from auth_security_extensions import install_security_extensions
    from admin_recovery import install_admin_recovery
    from login_diagnostics import install_login_diagnostics

    install_auth(app, db)
    install_authorization(app)
    install_security_extensions(app, db)
    install_admin_recovery(app, db)
    install_login_diagnostics(app, db)

    # Read-only startup diagnostic. Never logs passwords or hashes.
    try:
        auth_ext = app.extensions.get("ezz_auth") or {}
        verify_password = auth_ext.get("verify_password")
        admin_username = "admin"
        admin_password = __import__("os").environ.get("ADMIN_PASSWORD", "")
        recovery_password = __import__("os").environ.get("ADMIN_RECOVERY_PASSWORD", "")
        with db._connect() as conn:
            row = conn.execute(
                "SELECT username, role, active, password_hash, last_login, session_version "
                "FROM users WHERE username=%s",
                (admin_username,),
            ).fetchone()
        if not row:
            app.logger.warning(
                "AUTH_DIAG: admin_found=0 admin_password_matches=0 recovery_password_matches=0"
            )
        else:
            pw_match = bool(
                admin_password
                and callable(verify_password)
                and verify_password(admin_password, row["password_hash"])
            )
            recovery_match = bool(
                recovery_password
                and callable(verify_password)
                and verify_password(recovery_password, row["password_hash"])
            )
            app.logger.info(
                "AUTH_DIAG: admin_found=1 role=%s active=%d admin_password_matches=%d "
                "recovery_password_matches=%d last_login_present=%d session_version=%s",
                row["role"],
                int(bool(row["active"])),
                int(pw_match),
                int(recovery_match),
                int(bool(row["last_login"])),
                row["session_version"],
            )
    except Exception as exc:
        app.logger.exception("AUTH_DIAG: startup probe failed: %s", type(exc).__name__)

    app._ezz_production_security_bootstrapped = True
    app.extensions["ezz_production_security"] = {"installed": True, "cloud": True}
    return True
