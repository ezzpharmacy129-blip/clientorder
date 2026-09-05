# سجل تنظيف الملفات — 2026-09-05

## Auth

| الملف | القرار | السبب |
|---|---|---|
| auth_bootstrap.py | حذف | نُقل المحتوى الحي إلى `auth/local.py`، وأصبح `app.py` يختار الوحدة حسب backend. |
| auth_pg.py | حذف | نُقل المحتوى الحي إلى `auth/postgres.py`، وأصبح `app.py` يختار الوحدة حسب backend. |
| auth_entry.py | حذف | مجرد compatibility shim يستورد `app.app` ولا يحتوي منطقًا مطلوبًا بعد توحيد نقطة التشغيل. |
| auth_security_extensions.py | حذف | نُقل المنطق إلى `auth/policy.py`. |
| auth_security_extensions_v2.py | حذف | لا يوجد مسار runtime يفعّله. كان يفرض سياسة أضيق على الموظف وقد يغيّر سلوك التشغيل الحالي؛ لم يتم تفعيله تلقائيًا. |

## Fix / Patch

| الملف | القرار | السبب |
|---|---|---|
| cloud_db_update_fix.py | حذف | patch monkey-patch غير مستخدم؛ لا يوجد استدعاء runtime له في المسار الحالي. |
| pending_availability_fix.py | حذف | patch غير مستخدم، وكان يعتمد بدوره على ملفات safety أخرى غير مربوطة بنقطة التشغيل الحالية. |
| data_merge_safety.py | حذف | يحتوي منطق merge إضافيًا لكنه غير مربوط بمسار التطبيق الحالي؛ حذف الملف لا يزيل سلوكًا مستخدمًا فعليًا. تتم مراجعة semantics للاستيراد/الاستعادة لاحقًا كوظيفة مستقلة إن لزم. |
| cloud_integration_safety.py | حذف | wrapper غير مستخدم حاليًا؛ الحل الموحد أصبح داخل startup الرئيسي والطبقة الخلفية. |
| EXPORT_FIX_TRIGGER.txt | حذف | ملف trigger وصفي فقط، لا يضيف وظيفة وقت التشغيل. |

## Runtime wiring

| الملف | القرار | السبب |
|---|---|---|
| wsgi_config.py | حذف | كان نقطة تشغيل ثانية غير مستخدمة من `render.yaml`، ويكرر تهيئة auth/extensions. |
| gunicorn.conf.py | حذف | `render.yaml` يحدد start command مباشرة إلى `gunicorn app:app`، لذلك هذا الملف يخلق مسار تهيئة موازيًا ومربكًا. |

## ملاحظة

`postrollback_export.py` لم يُحذف لأنه مستخدم مباشرة من التطبيق، مع تنظيف مسارات التهيئة حوله.
