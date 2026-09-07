import unittest
from pathlib import Path

class P15ImportExportUXTests(unittest.TestCase):
    def test_current_excel_export_route_exists(self):
        s=Path("app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/data/export-xlsx")',s)
        self.assertIn('download_name=f"Ezz_Pharmacy_Data_',s)
    def test_import_reports_backup_and_order_count(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("Safety Backup:",s)
        self.assertIn("d.order_count||0",s)
    def test_export_buttons_have_handlers(self):
        s=Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('export-current-data-btn',s)
        self.assertIn('export-postrollback-btn',s)
    def test_backup_ui_explains_formats(self):
        s=Path("templates/index.html").read_text(encoding="utf-8")
        self.assertIn("<b>Excel:</b>",s)
        self.assertIn("<b>ZIP:</b>",s)
if __name__=="__main__": unittest.main()
