# إصلاح نشر Render – الإصدار 1.3.1

سبب خطأ `TemplateNotFound: index.html` هو أن Render لم يجد مجلد `templates` داخل جذر المشروع أو أن هيكل المستودع لا يطابق الحزمة. هذه النسخة تجعل مسارات templates/static مطلقة، وتصلح معالج أخطاء Flask.

## قبل إعادة النشر
يجب أن يكون جذر مستودع GitHub يحتوي مباشرةً على:
- `app.py`
- `db.py`
- `cloud_db.py`
- `requirements.txt`
- `templates/index.html`
- `static/`
- `render.yaml`

## Render
Build Command:
```
pip install -r requirements.txt
```
Start Command:
```
python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

ثم نفّذ `Manual Deploy -> Clear build cache & deploy`.
