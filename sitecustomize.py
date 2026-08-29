# -*- coding: utf-8 -*-
"""Safe runtime wiring for the Render deployment."""
import os
import flask
from flask import redirect, session, request, Response

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

        # Controlled one-time clean restart. The operation creates an automatic
        # cloud backup first and then clears only operational records.
        try:
            from one_time_reset import reset_if_requested
            reset_if_requested(db_obj)
        except Exception:
            pass

        cloud_mod = __import__("cloud_db", fromlist=["CloudDB"])
        CloudDB = cloud_mod.CloudDB
        if not getattr(CloudDB, "_ezz_runtime_safeguards_v2", False):
            original_log = CloudDB._log

            def audit_log(self, conn, order_id, action, old_status, new_status, note, user):
                return original_log(
                    self, conn, order_id, action, old_status, new_status, note,
                    _current_session_user(),
                )
            CloudDB._log = audit_log

            original_import = CloudDB.import_legacy_data

            def safe_import(self, source_path):
                pre_backup = None
                try:
                    pre_backup = self.create_manual_backup(reason="auto")
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
                    self.create_manual_backup(reason="auto")
                except Exception:
                    pass
                return original_delete(self, order_id, user=_current_session_user())
            CloudDB.delete_order = safe_delete

            CloudDB._ezz_runtime_safeguards_v2 = True

        from cloud_db_update_fix import install_cloud_order_update_fix
        install_cloud_order_update_fix(db_obj)
    except Exception:
        # Optional safeguards must never prevent the application from starting.
        pass


def _protected_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)

    from auth_bootstrap import install_auth
    from auth_security_extensions import install_security_extensions
    from admin_state_controls import install_admin_state_controls
    from pending_availability_fix import install_pending_availability_fix
    from data_export import install_data_export
    from postrollback_export import install_postrollback_export
    from db import db

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

    legacy_paths = {
        "/static/undo-ui.js",
        "/static/order-form-fix.js",
        "/static/production-order-fix.js",
        "/static/ui-behavior-fix.js",
        "/static/ui-routing-fix.js",
        "/static/modal-bootstrap.js",
        "/static/ui-bootstrap.js",
    }

    @self.before_request
    def _disable_legacy_ui_patches():
        if request.path in legacy_paths:
            response = Response(
                "/* legacy frontend patch intentionally disabled; app.js is the single UI source */",
                mimetype="application/javascript",
            )
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return response
        return None

    @self.after_request
    def _stabilize_frontend(response):
        try:
            if response.mimetype != "text/html" or response.status_code != 200:
                return response

            body = response.get_data(as_text=True)

            # Remove all legacy frontend script tags from the rendered page.
            for src in (
                "/static/undo-ui.js",
                "/static/order-form-fix.js",
                "/static/production-order-fix.js",
                "/static/ui-behavior-fix.js",
                "/static/ui-routing-fix.js",
                "/static/modal-bootstrap.js",
                "/static/ui-bootstrap.js",
            ):
                body = body.replace(f'<script src="{src}"></script>', "")

            # Force a fresh browser copy of the real frontend assets after the fix.
            body = body.replace("/static/style.css'", "/static/style.css?v=20260829-modal2'")
            body = body.replace("/static/style.css\"", "/static/style.css?v=20260829-modal2\"")
            body = body.replace("/static/app.js'", "/static/app.js?v=20260829-modal2'")
            body = body.replace("/static/app.js\"", "/static/app.js?v=20260829-modal2\"")

            # The core app.js expects these elements during its DOMContentLoaded setup.
            # Put them into the page itself so there is no timing dependency or duplicate JS bootstrap.
            if 'id="order-modal"' not in body and "</body>" in body:
                modal_html = '''
<div id="order-modal" class="modal-overlay hidden" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-header">
      <h3 id="modal-title">تفاصيل الطلب</h3>
      <button id="modal-close-btn" type="button" class="modal-close" aria-label="إغلاق">✕</button>
    </div>
    <div id="modal-body" class="modal-body"></div>
  </div>
</div>
<div id="availability-modal" class="modal-overlay hidden" aria-hidden="true">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="availability-title">
    <div class="modal-header">
      <h3 id="availability-title">تحديث توفر المنتجات</h3>
      <button id="availability-close-btn" type="button" class="modal-close" aria-label="إغلاق">✕</button>
    </div>
    <div id="availability-items" class="modal-body"></div>
    <div class="modal-actions">
      <button id="availability-save-btn" type="button" class="btn btn-primary">حفظ حالة التوفر</button>
      <button id="availability-cancel-btn" type="button" class="btn btn-secondary">إلغاء</button>
    </div>
  </div>
</div>
<div id="confirm-modal" class="modal-overlay hidden" aria-hidden="true">
  <div class="modal small" role="dialog" aria-modal="true">
    <div class="modal-header">
      <h3>تأكيد العملية</h3>
      <button id="confirm-no-btn" type="button" class="modal-close">✕</button>
    </div>
    <div id="confirm-message" class="modal-body"></div>
    <div class="modal-actions">
      <button id="confirm-yes-btn" type="button" class="btn btn-danger">تأكيد</button>
      <button id="confirm-no-btn-2" type="button" class="btn btn-secondary">إلغاء</button>
    </div>
  </div>
</div>
<div id="postpone-modal" class="modal-overlay hidden" aria-hidden="true">
  <div class="modal small" role="dialog" aria-modal="true">
    <div class="modal-header">
      <h3>تأجيل المتابعة</h3>
      <button id="postpone-close-btn" type="button" class="modal-close">✕</button>
    </div>
    <div class="modal-body">
      <div class="postpone-options">
        <button type="button" class="btn btn-outline postpone-quick" data-days="1">غدًا</button>
        <button type="button" class="btn btn-outline postpone-quick" data-days="3">بعد 3 أيام</button>
        <button type="button" class="btn btn-outline postpone-quick" data-days="7">بعد أسبوع</button>
        <input id="postpone-custom-date" type="date">
      </div>
    </div>
    <div class="modal-actions">
      <button id="postpone-custom-confirm" type="button" class="btn btn-primary">حفظ</button>
    </div>
  </div>
</div>
'''
                body = body.replace("</body>", modal_html + "</body>", 1)

            response.set_data(body)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        except Exception:
            pass
        return response


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v5", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v5 = True

_install_runtime_safeguards()
