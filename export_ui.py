# -*- coding: utf-8 -*-
"""Inject a visible read-only Excel export button into the existing UI."""
from flask import request

def install_export_ui(app):
    if getattr(app, '_ezz_export_ui_installed', False):
        return
    app._ezz_export_ui_installed = True

    @app.after_request
    def inject_export_button(response):
        try:
            if request.path != '/' or response.status_code != 200:
                return response
            content_type = response.headers.get('Content-Type','')
            if 'text/html' not in content_type:
                return response
            html = response.get_data(as_text=True)
            marker = 'id="create-backup-btn"'
            if 'id="export-current-data-btn"' in html or marker not in html:
                return response
            button = '''<button class="btn btn-outline" id="export-current-data-btn" type="button">📤 تصدير البيانات إلى Excel</button><script>(function(){var b=document.getElementById('export-current-data-btn');if(!b)return;b.addEventListener('click',function(){window.location.href='/api/data/export-xlsx';});})();</script>'''
            html = html.replace('</div><div class="backup-notice">', button + '</div><div class="backup-notice">', 1)
            response.set_data(html)
            return response
        except Exception:
            return response
