# -*- coding: utf-8 -*-
"""Inject read-only recovery export button into the existing UI."""
from flask import request


def install_export_ui(app):
    if getattr(app, '_ezz_export_ui_installed', False):
        return
    app._ezz_export_ui_installed = True

    @app.after_request
    def inject_export_buttons(response):
        try:
            if request.path != '/' or response.status_code != 200:
                return response
            if 'text/html' not in response.headers.get('Content-Type', ''):
                return response
            html = response.get_data(as_text=True)
            if 'id="export-postrollback-btn"' in html:
                return response

            script = r'''<script>(function(){function add(){if(document.getElementById('export-postrollback-btn'))return;var host=document.querySelector('#view-backups .backup-head-actions')||document.querySelector('#view-backups .panel-header')||document.getElementById('view-backups');if(!host)return;var b=document.createElement('button');b.id='export-postrollback-btn';b.type='button';b.className='btn btn-outline';b.textContent='🛟 استخراج بيانات ما قبل الـRollback';b.style.marginInlineStart='8px';b.addEventListener('click',function(){window.location.href='/api/data/export-postrollback';});host.appendChild(b);}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',add);else add();setTimeout(add,500);setTimeout(add,1500);})();</script>'''
            if '</body>' in html:
                html = html.replace('</body>', script + '</body>', 1)
            else:
                html += script
            response.set_data(html)
            return response
        except Exception:
            return response
