import unittest
from pathlib import Path

class P16PermissionMatrixTests(unittest.TestCase):
    def test_matrix_has_both_roles(self):
        s=Path("authorization_policy.py").read_text(encoding="utf-8")
        self.assertIn('"employee": {',s)
        self.assertIn('"admin": {',s)
        self.assertIn('"permission_matrix": PERMISSION_MATRIX',s)

    def test_admin_boundary_is_centralized(self):
        s=Path("authorization_policy.py").read_text(encoding="utf-8")
        self.assertIn('path.startswith(ADMIN_PREFIXES)',s)
        self.assertIn('ADMIN_PREFIXES = (',s)
        self.assertIn('/api/admin/',s)
        self.assertIn('/admin/',s)

    def test_auth_module_no_longer_duplicates_admin_decorator(self):
        s=Path("auth_pg.py").read_text(encoding="utf-8")
        self.assertNotIn('def admin_only(fn):',s)
        self.assertNotIn('@admin_only',s)

    def test_destructive_permissions_remain_restricted(self):
        s=Path("authorization_policy.py").read_text(encoding="utf-8")
        self.assertIn('"delete_order": False',s)
        self.assertIn('"import": False',s)
        self.assertIn('"restore": False',s)
        self.assertIn('"reset": False',s)
        self.assertIn('"delete_order": True',s)
        self.assertIn('"import": True',s)
        self.assertIn('"restore": True',s)
        self.assertIn('"reset": True',s)

if __name__=="__main__":
    unittest.main()
