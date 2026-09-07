# -*- coding: utf-8 -*-
"""Single source of truth for dashboard actionable categories.

The dashboard has historically had separate Python and SQL definitions for
follow-up categories. This module centralizes the operational projection used
by the API response so counters and lists cannot disagree.
"""
import json
from datetime import date

from flask import jsonify

from db import (
    db,
    CLOSED_STATUSES,
    STATUS_PENDING,
    STATUS_AVAILABLE,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    STATUS_CONTACTED,
    STATUS_NOT_PICKED,
    CONTACT_NOT_CONTACTED,
    CONTACT_AWAITING,
    today_str,
)

ACTION_KEYS = ("overdue", "today", "awaiting_reply", "needs_supply")


def classify_action(order, today):
    status = str(order.get("Status") or "").strip()
    contact = str(order.get("Contact_Status") or "").strip()
    next_followup = str(order.get("Next_Followup_Date") or "").strip()

    if status in CLOSED_STATUSES:
        return None

    followup_candidate = (
        (status in (STATUS_AVAILABLE, STATUS_PARTIAL, STATUS_UNAVAILABLE)
         and contact in ("", CONTACT_NOT_CONTACTED))
        or contact == CONTACT_AWAITING
        or status in (STATUS_CONTACTED, STATUS_NOT_PICKED)
    )

    if followup_candidate and next_followup and next_followup < today:
        try:
            due = date.fromisoformat(next_followup)
            now = date.fromisoformat(today)
            hint = f"متأخر منذ {max(1, (now - due).days)} يوم"
        except ValueError:
            hint = "موعد المتابعة تجاوز اليوم"
        return {
            "action_key": "overdue",
            "priority": 0,
            "next_action": "متابعة عاجلة",
            "action_hint": hint,
        }

    if followup_candidate and next_followup == today:
        return {
            "action_key": "today",
            "priority": 1,
            "next_action": "متابعة العميل",
            "action_hint": "موعد المتابعة اليوم",
        }

    if contact == CONTACT_AWAITING:
        return {
            "action_key": "awaiting_reply",
            "priority": 2,
            "next_action": "انتظار رد العميل",
            "action_hint": "الرسالة أُرسلت وننتظر رد العميل",
        }

    pending_items = [
        item for item in (order.get("Items") or [])
        if str(item.get("Availability_Status") or "").strip() == "بانتظار التوفر"
        and str(item.get("Customer_Decision") or "").strip().lower() != "rejected"
    ]
    if status == STATUS_PENDING or pending_items:
        return {
            "action_key": "needs_supply",
            "priority": 3,
            "next_action": "متابعة التوفير",
            "action_hint": f"يوجد {len(pending_items) if pending_items else 1} منتج بانتظار التوفر",
        }

    return None


def _row(order, action):
    shortage_count = sum(
        1 for item in (order.get("Items") or [])
        if str(item.get("Availability_Status") or "").strip() == "بانتظار التوفر"
        and str(item.get("Customer_Decision") or "").strip().lower() != "rejected"
    )
    return {
        "Order_ID": order.get("Order_ID", ""),
        "Customer_Name": order.get("Customer_Name", ""),
        "Phone": order.get("Phone", ""),
        "Status": order.get("Status", ""),
        "Contact_Status": order.get("Contact_Status", ""),
        "Next_Followup_Date": order.get("Next_Followup_Date", ""),
        "Created_At": order.get("Created_At", ""),
        "action_key": action["action_key"],
        "priority": action["priority"],
        "next_action": action["next_action"],
        "action_hint": action["action_hint"],
        "shortage_count": shortage_count,
    }


def build_action_center(orders, today=None):
    today = today or today_str()
    grouped = {key: [] for key in ACTION_KEYS}
    for order in orders:
        action = classify_action(order, today)
        if action:
            grouped[action["action_key"]].append(_row(order, action))

    for rows in grouped.values():
        rows.sort(key=lambda row: (
            int(row.get("priority", 99)),
            str(row.get("Next_Followup_Date") or "9999-99-99"),
            str(row.get("Created_At") or ""),
        ))

    items = []
    for key in ACTION_KEYS:
        items.extend(grouped[key])

    return {
        "summary": {key: len(grouped[key]) for key in ACTION_KEYS},
        "total_actionable": len(items),
        "items": items[:50],
    }


def _dashboard_payload_from_response(response):
    try:
        payload = response.get_json(silent=True)
    except Exception:
        payload = None
    return payload if isinstance(payload, dict) else None


def install_dashboard_source_of_truth(app):
    """Normalize dashboard JSON after the legacy route has built it.

    This is intentionally installed at the API boundary so old dashboard
    calculation paths cannot make the visible counters disagree with the
    visible lists. The legacy data/storage APIs remain untouched.
    """
    if app.extensions.get("dashboard_source_of_truth_installed"):
        return
    app.extensions["dashboard_source_of_truth_installed"] = True

    @app.after_request
    def _dashboard_source_of_truth(response):
        if response.status_code != 200 or request_path := getattr(response, "_request_path", None):
            # Flask responses do not normally carry request path metadata.
            # The actual path check below uses the request context.
            pass
        try:
            from flask import request
            path = request.path
        except Exception:
            return response

        if path not in {"/api/dashboard", "/api/action-center"} or response.status_code != 200:
            return response

        payload = _dashboard_payload_from_response(response)
        if payload is None:
            return response

        orders = db.get_all_orders()
        today = today_str()
        action_center = build_action_center(orders, today)

        if path == "/api/action-center":
            action_center["updated_at"] = payload.get("updated_at", "")
            response.set_data(json.dumps(action_center, ensure_ascii=False, separators=(",", ":")))
            response.headers["Content-Type"] = "application/json"
            return response

        payload["action_center"] = action_center
        payload["overdue"] = action_center["summary"]["overdue"]
        payload["today_followup"] = action_center["summary"]["today"]

        filters = payload.get("dashboard_filters")
        if isinstance(filters, dict):
            dashboard_orders = filters.get("all") or payload.get("orders") or []
            by_id = {str(row.get("Order_ID")): row for row in dashboard_orders if isinstance(row, dict)}
            filters["overdue"] = [by_id[str(row["Order_ID"])] for row in action_center["items"] if row["action_key"] == "overdue" and str(row["Order_ID"]) in by_id]
            filters["today_followup"] = [by_id[str(row["Order_ID"])] for row in action_center["items"] if row["action_key"] == "today" and str(row["Order_ID"]) in by_id]

        response.set_data(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        response.headers["Content-Type"] = "application/json"
        return response
