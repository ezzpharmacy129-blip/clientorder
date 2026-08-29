# Minimal Gunicorn configuration for Render.
# Keep application logic out of this file.

bind = "0.0.0.0:10000"
workers = 1
threads = 4
timeout = 120
