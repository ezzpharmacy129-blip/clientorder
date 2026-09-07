"""Temporary, non-secret diagnostics for the production login flow.

This module is intentionally read-only with respect to application data. It only
logs request/CSRF/session outcomes and credential-match booleans; it never logs
passwords, password hashes, session contents, CSRF values, or recovery secrets.
Remove after the login issue is identified.
"""
from functools import wraps
from flask import g, request, session


def install_login_diagnostics(app, db):
    if getattr(app, "_ezz_login_diagnostics_installed", False):
        return True

    endpoint = "ezz_login"
    original = app.view_functions.get(endpoint)
    if original is None:
        app.logger.warning("LOGIN_DIAG: login endpoint not found during diagnostics installation")
        return False

    try:
        verify_password = (app.extensions.get("ezz_auth") or {}).get("verify_password")
    except Exception:
        verify_password = None

    @wraps(original)
    def diagnostic_login_view(*args, **kwargs):
        g.ezz_login_view_entered = True
        g.ezz_login_username_len = len(str(request.form.get("username") or "").strip())
        g.ezz_login_csrf_form_present = bool(str(request.form.get("csrf_token") or "").strip())

        user_found = False
        user_active = False
        password_matches = False
        username = str(request.form.get("username") or "").strip()
        if request.method == "POST" and username:
            try:
                with db._connect() as conn:
                    row = conn.execute(
                        "SELECT active, password_hash FROM users WHERE username=%s",
                        (username,),
                    ).fetchone()
                if row:
                    user_found = True
                    user_active = bool(row["active"])
                    if user_active and callable(verify_password):
                        password_matches = bool(
                            verify_password(
                                str(request.form.get("password") or ""),
                                row["password_hash"],
                            )
                        )
            except Exception as exc:
                app.logger.exception("LOGIN_DIAG: credential probe failed: %s", type(exc).__name__)

        g.ezz_login_user_found = user_found
        g.ezz_login_user_active = user_active
        g.ezz_login_password_matches = password_matches

        app.logger.info(
            "LOGIN_DIAG: view_entered=1 method=%s username_len=%d user_found=%d active=%d password_matches=%d csrf_form_present=%d",
            request.method,
            g.ezz_login_username_len,
            int(user_found),
            int(user_active),
            int(password_matches),
            int(g.ezz_login_csrf_form_present),
        )

        response = original(*args, **kwargs)

        app.logger.info(
            "LOGIN_DIAG: view_returned status=%s session_user_id=%d session_role=%d session_username=%d",
            getattr(response, "status_code", "unknown"),
            int(bool(session.get("user_id"))),
            int(bool(session.get("role"))),
            int(bool(session.get("username"))),
        )
        return response

    app.view_functions[endpoint] = diagnostic_login_view

    @app.after_request
    def login_diagnostic_response(response):
        if request.path == "/login" and request.method == "POST":
            app.logger.info(
                "LOGIN_DIAG: response status=%s view_entered=%d csrf_form_present=%d session_csrf_present=%d session_cookie_set=%d",
                response.status_code,
                int(bool(getattr(g, "ezz_login_view_entered", False))),
                int(bool(getattr(g, "ezz_login_csrf_form_present", False))),
                int(bool(session.get("_csrf_token"))),
                int("Set-Cookie" in response.headers),
            )
        return response

    app._ezz_login_diagnostics_installed = True
    return True
