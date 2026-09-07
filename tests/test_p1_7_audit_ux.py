import unittest
from pathlib import Path

class P17AuditUXTests(unittest.TestCase):
    def test_paginated_audit_query_exists(self):
        for name in ("cloud_db.py","db.py"):
            s=Path(name).read_text(encoding="utf-8")
            self.assertIn("def get_activity_log_page",s)
    def test_admin_audit_has_filters_and_before_after_columns(self):
        s=Path("auth_pg.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/admin/audit")',s)
        self.assertIn("بحث وتصفية",s)
        self.assertIn("قبل",s)
        self.assertIn("بعد",s)
        self.assertIn("page={prev}",s)
    def test_duplicate_destructive_guard_removed(self):
        s=Path("auth_pg.py").read_text(encoding="utf-8")
        self.assertNotIn("def admin_destructive_guard",s)
if __name__=="__main__": unittest.main()
