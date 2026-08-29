# -*- coding: utf-8 -*-
"""Make admin/audit/export extensions compatible with PostgreSQL CloudDB."""
import io
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import jsonify, send_file

_PATCHED = False


def install_cloud_integrations():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    import auth_security_extensions
    import data_export

    original_security = auth_security_extensions.install_security_extensions

    def security_wrapper(app, db):
        result = original_security(app, db)
        if db.__class__.__module__ == "cloud_db":
            auth = app.extensions.get("ezz_auth") or {}
            current_user = auth.get("current_user", lambda: None)

            def cloud_admin_audit():
                user = current_user()
                if not user:
                    return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
                if user.get("role") != "admin":
                    return jsonify({"error": "غير مصرح لك بهذا الإجراء"}), 403
                try:
                    from flask import request
                    limit = min(max(int(request.args.get("limit", 500)), 1), 2000)
                except (TypeError, ValueError):
                    limit = 500
                rows = db.get_activity_log()
                rows = rows[:limit]
                return jsonify({"logs": rows})

            if "admin_audit_api" in app.view_functions:
                app.view_functions["admin_audit_api"] = cloud_admin_audit
        return result

    auth_security_extensions.install_security_extensions = security_wrapper

    original_export = data_export.install_data_export

    def export_wrapper(app, db):
        result = original_export(app, db)
        if db.__class__.__module__ == "cloud_db":
            auth = app.extensions.get("ezz_auth") or {}
            current_user = auth.get("current_user", lambda: None)

            def export_cloud_xlsx():
                if not current_user():
                    return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
                try:
                    payload = db._workbook_bytes()
                    ts = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d_%H%M%S")
                    return send_file(
                        io.BytesIO(payload),
                        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        as_attachment=True,
                        download_name=f"Ezz_Pharmacy_Backup_{ts}.xlsx",
                        max_age=0,
                        conditional=False,
                    )
                except Exception as exc:
                    app.logger.exception("Cloud Excel export failed")
                    return jsonify({"error": f"تعذر تصدير البيانات: {exc}"}), 500

            if "export_current_xlsx" in app.view_functions:
                app.view_functions["export_current_xlsx"] = export_cloud_xlsx
        return result

    data_export.install_data_export = export_wrapper
