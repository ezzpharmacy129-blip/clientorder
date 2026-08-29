# -*- coding: utf-8 -*-
"""Load application extensions safely before Flask creates app:app."""
import os
import flask
from flask import redirect, url_for, session

_raw_db_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_db_url and not (_raw_db_url.startswith("postgres://") or _raw_db_url.startswith("postgresql://")):
    os.environ.pop("DATABASE_URL", None)

_original_init = flask.Flask.__init__


def _protected_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    from auth_bootstrap import install_auth
    from auth_security_extensions import install_security_extensions
    from admin_state_controls import install_admin_state_controls
    from pending_availability_fix import install_pending_availability_fix
    from data_export import install_data_export
    from export_ui import install_export_ui
    from postrollback_export import install_postrollback_export
    from db import db
    install_auth(self, db)
    # Safety net: ensure the template's logout endpoint always exists before
    # index.html is rendered, even if auth_bootstrap was already installed.
    if "ezz_logout" not in self.view_functions:
        @self.route("/logout", methods=["GET", "POST"], endpoint="ezz_logout")
        def _ezz_logout_fallback():
            session.clear()
            r = redirect("/login")
            r.headers["Cache-Control"] = "no-store"
            return r
    install_security_extensions(self, db)
    install_admin_state_controls(self, db)
    install_pending_availability_fix(db)
    install_data_export(self, db)
    install_export_ui(self)
    install_postrollback_export(self)


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v2", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v2 = True
