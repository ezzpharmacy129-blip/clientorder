# -*- coding: utf-8 -*-
"""Read-only Excel export of the current pharmacy data."""
import os
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import jsonify, send_file


def install_data_export(app, db):
    if getattr(app, "_ezz_data_export_installed", False):
        return
    app._ezz_data_export_installed = True
    auth = app.extensions.get("ezz_auth")
    current_user = auth.get("current_user") if auth else (lambda: None)

    @app.get("/api/data/export-xlsx")
    def export_current_xlsx():
        user = current_user()
        if not user:
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        if user.get("role") != "admin":
            return jsonify({"error": "صلاحية المدير مطلوبة"}), 403
        try:
            if db.__class__.__module__ == "cloud_db":
                payload = db._workbook_bytes()
                ts = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d_%H%M%S")
                return send_file(
                    BytesIO(payload),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    as_attachment=True,
                    download_name=f"Ezz_Pharmacy_Backup_{ts}.xlsx",
                    max_age=0,
                    conditional=False,
                )
            path = os.path.abspath(getattr(db, "DB_PATH", ""))
            if not path or not os.path.isfile(path):
                return jsonify({"error": "ملف البيانات غير موجود على الخادم"}), 404
            ts = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d_%H%M%S")
            return send_file(
                path,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"Ezz_Pharmacy_Backup_{ts}.xlsx",
                max_age=0,
                conditional=False,
            )
        except Exception as exc:
            app.logger.exception("Excel export failed")
            return jsonify({"error": "تعذر تصدير البيانات"}), 500
