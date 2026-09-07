import unittest
from pathlib import Path

class DomContentRegressionTests(unittest.TestCase):
    def test_backup_handler_is_closed_before_export_handlers(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        start=s.index('document.addEventListener("DOMContentLoaded",')
        tail=s[start:]
        self.assertLess(tail.index('loadBackups();'), tail.index('export-current-data-btn'))
        self.assertIn('loadDashboard();', tail)
    def test_export_handlers_are_top_level_dom_ready_handlers(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        start=s.index('document.addEventListener("DOMContentLoaded",')
        tail=s[start:]
        self.assertIn('document.getElementById("export-current-data-btn")?.addEventListener',tail)
        self.assertIn('document.getElementById("export-postrollback-btn")?.addEventListener',tail)
if __name__=="__main__": unittest.main()
