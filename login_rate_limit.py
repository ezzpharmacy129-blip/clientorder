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
