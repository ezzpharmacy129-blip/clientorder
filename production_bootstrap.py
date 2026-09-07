"""Centralized PostgreSQL production security bootstrap.

The operation is intentionally idempotent because Gunicorn can call it after
Flask has already imported the application module.
"""


def install_production_security(app, db):
    """Install PostgreSQL authentication and authorization exactly once."""
    if db.__class__.__module__ != "cloud_db":
        return False

    from auth_pg import install_auth
    from authorization_policy import install_authorization
    from auth_security_extensions import install_security_extensions

    install_auth(app, db)
    install_authorization(app)
    install_security_extensions(app, db)
    app.extensions["ezz_production_security"] = {"installed": True, "cloud": True}
    return True
