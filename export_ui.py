# -*- coding: utf-8 -*-
"""Inject read-only Excel export buttons into the existing UI."""
from flask import request, session


def install_export_ui(app):
    if getattr(app, '_ezz_export_ui_installed', False):
        return
    app._ezz_export_ui_installed = True

    @app.after_request
    def inject_export_buttons(response):
        try:
            if request.path != '/' or response.status_code != 200:
                return response
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                return response
            html = response.get_data(as_text=True)

            marker = 'id="create-backup-btn"'
            if marker not in html:
                return response

            # Main current-data export button.
            if 'id="export-current-data-btn"' not in html:
                current_button = '''<button class="btn btn-outline" id="export-current-data-btn" type="button">📤 تصدير البيانات إلى Excel</button><script>(function(){var b=document.getElementById('export-current-data-btn');if(!b)return;b.addEventListener('click',function(){window.location.href='/api/data/export-xlsx';});})();</script>'''
                html = html.replace('</div><div class="backup-notice">', current_button + '</div><div class="backup-notice">', 1)

            # Admin-only recovery export from the PostgreSQL dataset that survived the rollback.
            username = str(session.get('username', '')).lower()
            role = str(session.get('role', '')).lower()
            is_admin = username in {'admin', 'administrator'} or role in {'admin', 'administrator'}
            if is_admin and 'id="export-postrollback-btn"' not in html:
                recovery_button = '''<button class="btn btn-outline" id="export-postrollback-btn" type="button">🛟 استخراج بيانات ما قبل الـRollback</button><script>(function(){var b=document.getElementById('export-postrollback-btn');if(!b)return;b.addEventListener('click',function(){window.location.href='/api/data/export-postrollback';});})();</script>'''
                html = html.replace('</div><div class="backup-notice">', recovery_button + '</div><div class="backup-notice">', 1)

            response.set_data(html)
            return response
        except Exception:
            return response
