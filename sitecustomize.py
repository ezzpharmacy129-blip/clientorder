# -*- coding: utf-8 -*-
"""Minimal runtime wiring for the Render deployment."""
import os
import flask
from flask import redirect, session

_raw_db_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_db_url and not (_raw_db_url.startswith("postgres://") or _raw_db_url.startswith("postgresql://")):
    os.environ.pop("DATABASE_URL", None)

_original_init = flask.Flask.__init__


def _current_session_user():
    try:
        return str(session.get("username") or "").strip() or "موظف"
    except Exception:
        return "موظف"


def _install_runtime_safeguards():
    try:
        import db as db_module
        db_obj = getattr(db_module, "db", None)
        if db_obj is None or db_obj.__class__.__module__ != "cloud_db":
            return

        cloud_mod = __import__("cloud_db", fromlist=["CloudDB"])
        CloudDB = cloud_mod.CloudDB
        if not getattr(CloudDB, "_ezz_runtime_safeguards_v3", False):
            original_log = CloudDB._log

            def audit_log(self, conn, order_id, action, old_status, new_status, note, user):
                return original_log(self, conn, order_id, action, old_status, new_status, note, _current_session_user())

            CloudDB._log = audit_log

            original_import = CloudDB.import_legacy_data

            def safe_import(self, source_path):
                pre_backup = None
                try:
                    pre_backup = self.create_manual_backup()
                except Exception:
                    pass
                result = original_import(self, source_path)
                if isinstance(result, dict) and pre_backup and not result.get("backup"):
                    result["backup"] = pre_backup
                return result

            CloudDB.import_legacy_data = safe_import

            original_delete = CloudDB.delete_order

            def safe_delete(self, order_id, user="موظف"):
                try:
                    self.create_manual_backup()
                except Exception:
                    pass
                return original_delete(self, order_id, user=_current_session_user())

            CloudDB.delete_order = safe_delete
            CloudDB._ezz_runtime_safeguards_v3 = True

        from cloud_db_update_fix import install_cloud_order_update_fix
        install_cloud_order_update_fix(db_obj)
    except Exception:
        pass


def _protected_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)

    from db import db
    # Production uses PostgreSQL-native authentication/users/audit. Local builds
    # retain the existing SQLite/Excel fallback in auth_bootstrap.py.
    if db.__class__.__module__ == "cloud_db":
        from auth_pg import install_auth
    else:
        from auth_bootstrap import install_auth

    from auth_security_extensions import install_security_extensions
    from admin_state_controls import install_admin_state_controls
    from pending_availability_fix import install_pending_availability_fix
    from data_export import install_data_export
    from postrollback_export import install_postrollback_export

    install_auth(self, db)

    if "ezz_logout" not in self.view_functions:
        @self.route("/logout", methods=["GET", "POST"], endpoint="ezz_logout")
        def _ezz_logout_fallback():
            session.clear()
            response = redirect("/login")
            response.headers["Cache-Control"] = "no-store"
            return response

    install_security_extensions(self, db)
    install_admin_state_controls(self, db)
    if db.__class__.__module__ != "cloud_db":
        install_pending_availability_fix(db)
    install_data_export(self, db)
    install_postrollback_export(self)


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v6", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v6 = True

_install_runtime_safeguards()
