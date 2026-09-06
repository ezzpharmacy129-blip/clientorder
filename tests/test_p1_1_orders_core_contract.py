import unittest
from pathlib import Path

class OrdersCoreContractTests(unittest.TestCase):
    def test_production_contract_exists(self):
        self.assertTrue(Path("docs/ORDER_CORE.md").is_file())

    def test_cloud_backend_has_canonical_order_methods(self):
        source = Path("cloud_db.py").read_text(encoding="utf-8")
        for name in (
            "create_order", "update_order", "set_availability", "set_contact_status",
            "mark_pickup", "mark_not_picked", "postpone", "cancel_order",
            "delete_order", "undo_last", "set_item_image", "delete_item_image",
        ):
            self.assertIn(f"def {name}", source)

    def test_status_changes_are_not_allowed_via_generic_update(self):
        source = Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("تغيير حالة الطلب مباشرة غير مسموح", source)
        self.assertIn("تغيير حالة التواصل مباشرة غير مسموح", source)

    def test_item_identity_is_stable_for_update(self):
        source = Path("cloud_db.py").read_text(encoding="utf-8")
        self.assertIn("existing_by_id = {str(item['Item_ID']): item", source)
        self.assertIn("deleted_item_ids", source)

if __name__ == "__main__":
    unittest.main()
