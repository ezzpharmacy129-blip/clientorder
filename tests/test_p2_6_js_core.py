import unittest
from pathlib import Path

class P26JavaScriptCoreTests(unittest.TestCase):
    def test_core_contains_shared_utilities(self):
        s=Path("static/core.js").read_text(encoding="utf-8")
        for name in ("apiFetch","toast","setButtonLoading","esc","fmtDate","badge","todayISO"):
            self.assertIn(f"function {name}",s)

    def test_app_no_longer_duplicates_core_utilities(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        for name in ("apiFetch","toast","setButtonLoading","esc","fmtDate","badge","todayISO"):
            self.assertNotIn(f"function {name}",s)

    def test_core_loads_before_app(self):
        s=Path("templates/index.html").read_text(encoding="utf-8")
        core=s.index('filename='core.js'')
        app=s.index('filename='app.js'')
        self.assertLess(core,app)

if __name__=="__main__":
    unittest.main()

# CI verification marker: test current PR head.
