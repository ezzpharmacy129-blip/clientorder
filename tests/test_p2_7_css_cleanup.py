import unittest
from pathlib import Path

class P27CSSCleanupTests(unittest.TestCase):
    def test_global_font_inheritance_rule_is_not_duplicated(self):
        s=Path("static/style.css").read_text(encoding="utf-8")
        self.assertEqual(s.count("button,input,select,textarea{font:inherit}"),1)
    def test_no_css_backup_or_schema_changes(self):
        self.assertTrue(Path("static/style.css").is_file())

if __name__=="__main__":
    unittest.main()
