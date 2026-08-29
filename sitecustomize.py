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
    if "ezz_logout" not in self.view_functions:
        @self.route("/logout", methods=["GET", "POST"], endpoint="ezz_logout")
        def _ezz_logout_fallback():
            session.clear(); r = redirect("/login"); r.headers["Cache-Control"] = "no-store"; return r
    install_security_extensions(self, db)
    install_admin_state_controls(self, db)
    install_pending_availability_fix(db)
    install_data_export(self, db)
    install_export_ui(self)
    install_postrollback_export(self)

if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v2", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v2 = True

def _current_session_user():
    try: return str(session.get("username") or "").strip() or "موظف"
    except Exception: return "موظف"

def _install_runtime_safeguards():
    try:
        import db as _db_module
        db_obj = getattr(_db_module, "db", None)
        if db_obj is None or db_obj.__class__.__module__ != "cloud_db": return
        cloud_mod = __import__("cloud_db", fromlist=["CloudDB"])
        CloudDB = cloud_mod.CloudDB
        if getattr(CloudDB, "_ezz_runtime_safeguards_v1", False): return
        original_log = CloudDB._log
        def audit_log(self, conn, order_id, action, old_status, new_status, note, user):
            return original_log(self, conn, order_id, action, old_status, new_status, note, _current_session_user())
        CloudDB._log = audit_log
        original_import = CloudDB.import_legacy_data
        def safe_import(self, source_path):
            pre_backup = None
            try: pre_backup = self.create_manual_backup(reason="auto")
            except Exception: pass
            result = original_import(self, source_path)
            if isinstance(result, dict) and pre_backup and not result.get("backup"): result["backup"] = pre_backup
            return result
        CloudDB.import_legacy_data = safe_import
        original_delete = CloudDB.delete_order
        def safe_delete(self, order_id, user="موظف"):
            try: self.create_manual_backup(reason="auto")
            except Exception: pass
            return original_delete(self, order_id, user=_current_session_user())
        CloudDB.delete_order = safe_delete
        CloudDB._ezz_runtime_safeguards_v1 = True
    except Exception: pass

try: _install_runtime_safeguards()
except Exception: pass

def _install_order_ui_patch_on_app(app):
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(root, "static", "production-order-fix.js")
        if os.path.isfile(script_path) and not getattr(app, "_ezz_order_ui_patch_v1", False):
            with open(script_path, "r", encoding="utf-8") as fh: script_src = fh.read()
            @app.after_request
            def _ezz_order_fix_injection(response):
                try:
                    if response.mimetype == "text/html":
                        body = response.get_data(as_text=True)
                        if "EZZ_PRODUCTION_ORDER_FIX_V1" not in body and "</body>" in body:
                            response.set_data(body.replace("</body>", "<script>/* EZZ_PRODUCTION_ORDER_FIX_V1 */\n" + script_src + "\n</script></body>"))
                except Exception: pass
                return response
            app._ezz_order_ui_patch_v1 = True
    except Exception: pass

def _install_routing_ui_patch_on_app(app):
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(root, "static", "ui-routing-fix.js")
        if not os.path.isfile(script_path) or getattr(app, "_ezz_routing_ui_patch_v1", False): return
        with open(script_path, "r", encoding="utf-8") as fh: script_src = fh.read()
        @app.after_request
        def _ezz_routing_ui_injection(response):
            try:
                if response.mimetype == "text/html":
                    body = response.get_data(as_text=True)
                    if "EZZ_UI_ROUTING_FIX_V1" not in body and "</body>" in body:
                        payload = "<script>/* EZZ_UI_ROUTING_FIX_V1 */\n" + script_src + "\n</script>"
                        response.set_data(body.replace("</body>", payload + "</body>"))
            except Exception: pass
            return response
        app._ezz_routing_ui_patch_v1 = True
    except Exception: pass

_old_ctor = flask.Flask.__init__
def _final_protected_init(self, *args, **kwargs):
    _old_ctor(self, *args, **kwargs)
    _install_order_ui_patch_on_app(self)
    _install_routing_ui_patch_on_app(self)

flask.Flask.__init__ = _final_protected_init
flask.Flask._ezz_auth_constructor_patched_v2 = True
