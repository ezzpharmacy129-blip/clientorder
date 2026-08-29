# -*- coding: utf-8 -*-
"""Load application extensions safely before Flask creates app:app."""
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
        cloud_mod = __import__("cloud_db", fromlist=["CloudDB"])
        CloudDB = cloud_mod.CloudDB
        if not getattr(CloudDB, "_ezz_runtime_safeguards_v1", False):
            original_log = CloudDB._log

            def audit_log(self, conn, order_id, action, old_status, new_status, note, user):
                return original_log(self, conn, order_id, action, old_status, new_status, note, _current_session_user())

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
            CloudDB._ezz_runtime_safeguards_v1 = True

        from cloud_db_update_fix import install_cloud_order_update_fix
        install_cloud_order_update_fix(db_obj)
    except Exception:
        # Never block application startup because an optional safeguard is unavailable.
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

    # The repository accumulated several frontend compatibility scripts that
    # redefine the same event handlers as static/app.js. Keep them available as
    # files for historical compatibility, but serve them as inert JavaScript so
    # there is exactly one source of truth for UI actions.
    _legacy_ui_patch_paths = {
        "/static/undo-ui.js",
        "/static/order-form-fix.js",
        "/static/production-order-fix.js",
        "/static/ui-behavior-fix.js",
        "/static/ui-routing-fix.js",
        "/static/modal-bootstrap.js",
    }

    @self.before_request
    def _disable_legacy_ui_patches():
        if request.path in _legacy_ui_patch_paths:
            response = Response("/* legacy UI compatibility script intentionally disabled */", mimetype="application/javascript")
            response.headers["Cache-Control"] = "no-store"
            return response
        return None

    @self.after_request
    def _ezz_ui_bootstrap(response):
        try:
            if response.mimetype == "text/html" and response.status_code == 200:
                body = response.get_data(as_text=True)
                scripts = ''
                if "ui-bootstrap.js" not in body and "</body>" in body:
                    scripts += '<script src="/static/ui-bootstrap.js"></script>'

                # Core DOM cleanup runs after app.js's existing initializer.
                if "EZZ_CORE_UI_STABILITY_V1" not in body and "</body>" in body:
                    scripts += '''<script>/* EZZ_CORE_UI_STABILITY_V1 */
(function(){
  function stabilize(){
    const wrap=document.getElementById('product-items');
    if(wrap){
      const rows=[...wrap.querySelectorAll('.product-row')];
      if(rows.length>1){
        const keep=rows.find(r=>r.querySelector('.product-name')?.value?.trim() || r.querySelector('.product-image')?.files?.length) || rows[0];
        rows.forEach(r=>{if(r!==keep && !r.querySelector('.product-name')?.value?.trim() && !r.querySelector('.product-image')?.files?.length) r.remove()});
        if(typeof window.renumberProducts==='function') window.renumberProducts();
        if(typeof window.updateProductTotals==='function') window.updateProductTotals();
      }
    }

    const saveBtn=document.getElementById('availability-save-btn');
    if(saveBtn && typeof window.saveAvailability==='function' && !saveBtn.dataset.ezzCoreBound){
      saveBtn.dataset.ezzCoreBound='1';
      const originalSave=window.saveAvailability;
      saveBtn.onclick=async function(){
        await originalSave.apply(this,arguments);
        const a=document.getElementById('availability-modal');
        const o=document.getElementById('order-modal');
        if(a){a.classList.add('hidden');a.setAttribute('aria-hidden','true');}
        if(o){o.classList.add('hidden');o.setAttribute('aria-hidden','true');}
      };
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',stabilize,{once:true});
  else stabilize();
})();</script>'''

                if scripts:
                    response.set_data(body.replace("</body>", scripts + "</body>", 1))
        except Exception:
            pass
        return response


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v4", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v4 = True

_install_runtime_safeguards()
