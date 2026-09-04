# Gunicorn configuration for Render.
# Register the existing PostgreSQL export module after the worker loads app.

bind = "0.0.0.0:10000"
workers = 1
threads = 4
timeout = 120


def post_worker_init(worker):
    from app import app
    from postrollback_export import install_postrollback_export
    install_postrollback_export(app)
    from ai_assistant import install_ai
    install_ai(app)
    worker.log.info("Ezz Pharmacy Excel export route registered: /api/data/export-postrollback")
