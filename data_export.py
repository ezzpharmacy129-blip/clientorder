# -*- coding: utf-8 -*-
"""Read-only Excel export for the current application data."""
import os
from flask import jsonify, send_file
from datetime import datetime
from zoneinfo import ZoneInfo


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
        path = getattr(db, "DB_PATH", "")
        if not path or not os.path.exists(path):
            return jsonify({"error": "ملف البيانات غير موجود"}), 404
        # Read-only endpoint: never opens the workbook for writing and never changes data.
        ts = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d_%H%M%S")
        return send_file(path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"Ezz_Pharmacy_Backup_{ts}.xlsx")
