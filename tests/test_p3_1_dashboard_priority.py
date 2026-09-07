import unittest
from pathlib import Path


class P31DashboardPriorityTests(unittest.TestCase):
    def test_operational_action_center_precedes_stats(self):
        source = Path("templates/index.html").read_text(encoding="utf-8")
        dashboard_start = source.index('<section id="view-dashboard"')
        dashboard_end = source.index('<section id="view-shortages"', dashboard_start)
        dashboard = source[dashboard_start:dashboard_end]
        self.assertLess(
            dashboard.index('id="action-center"'),
            dashboard.index('class="stats-grid"'),
        )

    def test_action_center_keeps_four_operational_categories(self):
        source = Path("templates/index.html").read_text(encoding="utf-8")
        dashboard_start = source.index('<section id="view-dashboard"')
        dashboard_end = source.index('<section id="view-shortages"', dashboard_start)
        dashboard = source[dashboard_start:dashboard_end]
        for category in ("overdue", "needs_supply", "awaiting_reply", "today"):
            self.assertIn(f'data-action-category="{category}"', dashboard)

    def test_dashboard_priority_css_orders_critical_stats_first(self):
        css = Path("static/action_center.css").read_text(encoding="utf-8")
        expected_order = (
            'data-dashboard-filter="overdue"',
            'data-dashboard-filter="pending"',
            'data-dashboard-filter="awaiting_reply"',
            'data-dashboard-filter="available"',
            'data-dashboard-filter="pickup_pending"',
            'data-dashboard-filter="today_followup"',
            'data-dashboard-filter="picked_up"',
            'data-dashboard-filter="total"',
        )
        positions = [css.index(value) for value in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Dashboard Priority", css)

    def test_reference_stats_are_deemphasized_without_changing_markup(self):
        css = Path("static/action_center.css").read_text(encoding="utf-8")
        self.assertIn('data-dashboard-filter="total"', css)
        self.assertIn('data-dashboard-filter="picked_up"', css)
        self.assertIn(".stat-card.stat-reference", css)


if __name__ == "__main__":
    unittest.main()
