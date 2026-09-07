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
    app._ezz_production_security_bootstrapped = True
    app.extensions["ezz_production_security"] = {"installed": True, "cloud": True}
    return True
