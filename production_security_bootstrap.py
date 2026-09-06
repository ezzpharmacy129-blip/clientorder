"""Single startup integration point for production authentication/authorization."""


def install_production_security(app):
    """Enable PostgreSQL auth and server-side authorization for the live app."""
    try:
        from db import db
    except Exception:
        return False

    if db.__class__.__module__ != "cloud_db":
        return False

    from auth_pg import install_auth
    from authorization_policy import install_authorization

    install_auth(app, db)
    install_authorization(app)
    return True
