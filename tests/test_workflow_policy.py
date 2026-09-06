import unittest

from workflow_policy import validate_pickup, validate_not_picked, validate_status_override


class WorkflowPolicyTests(unittest.TestCase):
    def order(self, status="تم التواصل - بانتظار الاستلام", contact="العميل موافق"):
        return {"Status": status, "Contact_Status": contact}

    def item(self, availability="متوفر", decision=""):
        return {"Product_Name": "منتج تجريبي", "Availability_Status": availability, "Customer_Decision": decision}

    def test_pickup_requires_all_active_items_available(self):
        error = validate_pickup(
            self.order(),
            [self.item("متوفر"), self.item("بانتظار التوفر")],
        )
        self.assertIsNotNone(error)

    def test_pickup_requires_customer_acceptance(self):
        error = validate_pickup(
            self.order(contact="بانتظار رد العميل"),
            [self.item("متوفر")],
        )
        self.assertIsNotNone(error)

    def test_pickup_is_allowed_when_workflow_is_ready(self):
        self.assertIsNone(
            validate_pickup(
                self.order(),
                [self.item("متوفر"), self.item("متوفر")],
            )
        )

    def test_rejected_items_do_not_block_pickup(self):
        self.assertIsNone(
            validate_pickup(
                self.order(),
                [self.item("متوفر"), self.item("غير متوفر", "rejected")],
            )
        )

    def test_not_picked_requires_picked_up_state(self):
        self.assertIsNotNone(
            validate_not_picked(self.order("تم التواصل - بانتظار الاستلام"), [self.item()])
        )

    def test_not_picked_is_allowed_after_pickup(self):
        self.assertIsNone(
            validate_not_picked(self.order("تم الاستلام"), [self.item()])
        )

    def test_direct_status_override_is_rejected(self):
        self.assertIsNotNone(
            validate_status_override("بانتظار التوفر", "تم الاستلام")
        )

if __name__ == "__main__":
    unittest.main()
