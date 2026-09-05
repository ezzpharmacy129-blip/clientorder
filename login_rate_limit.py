"""In-memory login throttling for the production auth flow."""
import time
import threading

MAX_FAILURES = 5
WINDOW_SECONDS = 600

_attempts = {}
_lock = threading.Lock()

def key(remote_addr, username):
    return (str(remote_addr or "unknown"), str(username or "").strip().lower())

def is_limited(remote_addr, username, now=None):
    now = time.time() if now is None else float(now)
    k = key(remote_addr, username)
    cutoff = now - WINDOW_SECONDS
    with _lock:
        values = [t for t in _attempts.get(k, []) if t > cutoff]
        if values:
            _attempts[k] = values
        else:
            _attempts.pop(k, None)
    if len(values) < MAX_FAILURES:
        return False, 0
    return True, max(1, int((values[0] + WINDOW_SECONDS) - now))

def record_failure(remote_addr, username, now=None):
    now = time.time() if now is None else float(now)
    k = key(remote_addr, username)
    cutoff = now - WINDOW_SECONDS
    with _lock:
        values = [t for t in _attempts.get(k, []) if t > cutoff]
        values.append(now)
        _attempts[k] = values
    retry_after = max(1, int((values[0] + WINDOW_SECONDS) - now))
    return len(values), retry_after

def clear(remote_addr, username):
    with _lock:
        _attempts.pop(key(remote_addr, username), None)


def install(app):
    if getattr(app, "_ezz_login_rate_limit_installed", False):
        return
    app._ezz_login_rate_limit_installed = True

    from flask import jsonify, request

    @app.before_request
    def _login_throttle():
        if request.path != "/login" or request.method != "POST":
            return None

        remote = request.remote_addr or "unknown"
        username = request.form.get("username") or ""

        limited, retry_after = is_limited(remote, username)
        if limited:
            response = jsonify({
                "error": "تم تجاوز عدد محاولات تسجيل الدخول. حاول مرة أخرى لاحقًا.",
                "code": "login_rate_limited",
                "retry_after": retry_after,
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        return None

    @app.after_request
    def _record_login_result(response):
        if request.path == "/login" and request.method == "POST":
            remote = request.remote_addr or "unknown"
            username = request.form.get("username") or ""
            if response.status_code == 401:
                record_failure(remote, username)
            elif response.status_code in (302, 303, 307, 308):
                clear(remote, username)
        return response
