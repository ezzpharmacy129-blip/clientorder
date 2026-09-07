"""Explicit production runtime wiring for Gunicorn.

Production uses CloudDB/PostgreSQL for all operational data and authentication.
Authentication is initialized explicitly here; no Flask constructor monkey-patching
or Excel/SQLite authentication is used in the cloud service.

Important: user credentials are stored in PostgreSQL and are persistent. Render
environment variables are not treated as a password-reset mechanism on every boot.
"""


def on_starting(server):
    from app import app
    from db import db

    if db.__class__.__module__ != "cloud_db":
        raise RuntimeError("Render production requires the CloudDB/PostgreSQL backend")

    from auth_pg import install_auth
    install_auth(app, db)

    from authorization_policy import install_authorization
    install_authorization(app)

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
