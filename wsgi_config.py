"""Explicit production runtime wiring for Gunicorn.

Authentication and production extensions are initialized through a normal
Gunicorn config hook. This removes the runtime's dependency on Flask
constructor monkey-patching for security-critical initialization.
"""

def on_starting(server):
    from app import app
    from db import db

    is_cloud = db.__class__.__module__ == "cloud_db"

    if is_cloud:
        from auth_pg import install_auth
    else:
        from auth_bootstrap import install_auth
    install_auth(app, db)

    from auth_security_extensions import install_security_extensions
    install_security_extensions(app, db)

    from data_export import install_data_export
    install_data_export(app, db)

    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)

    if not is_cloud:
        from admin_state_controls import install_admin_state_controls
        from pending_availability_fix import install_pending_availability_fix
        install_admin_state_controls(app, db)
        install_pending_availability_fix(db)

    server.log.info("Ezz Pharmacy explicit runtime wiring initialized")
