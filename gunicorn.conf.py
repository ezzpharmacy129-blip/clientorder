# Gunicorn configuration for Render.
# PostgreSQL authentication, authorization and CSRF are initialized before workers serve requests.

bind = "0.0.0.0:10000"
workers = 1
threads = 4
timeout = 120


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
    server.log.info("Ezz Pharmacy production authentication and authorization initialized")


def post_worker_init(worker):
    from app import app
    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)
    from ai_assistant import install_ai
    install_ai(app)
    worker.log.info("Ezz Pharmacy Excel export route registered: /api/data/export-postrollback")
