# -*- coding: utf-8 -*-
"""Read-only Excel export for the current application data."""
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import jsonify, send_file
from openpyxl import Workbook


def _write_sheet(ws, headers, rows):
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    ws.freeze_panes = "A2"
    if headers:
        ws.auto_filter.ref = ws.dimensions


def _build_workbook(db):
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"

    orders = db.get_all_orders() or []
    order_headers = [
        "Order_ID", "Customer_Name", "Phone", "Product_Name", "Quantity",
        "Order_Date", "Available_Date", "Status", "Contact_Status",
        "Last_Contact_Date", "Next_Followup_Date", "Pickup_Date", "Notes",
        "Created_At", "Updated_At"
    ]
    _write_sheet(ws, order_headers, orders)

    items = []
    for order in orders:
        for item in order.get("Items", []) or []:
            row = dict(item)
            row.setdefault("Order_ID", order.get("Order_ID", ""))
            items.append(row)
    item_headers = [
        "Item_ID", "Order_ID", "Product_Name", "Quantity", "Image_Path",
        "Availability_Status", "Available_Price", "Discounted_Price",
        "Unavailable_Reason", "Availability_Note",
        "Price_Confirmation_Required", "Available_At", "Created_At"
    ]
    _write_sheet(wb.create_sheet("Order_Items"), item_headers, items)

    log_rows = []
    getter = getattr(db, "get_activity_log", None)
    if getter:
        try:
            log_rows = getter() or []
        except Exception:
            log_rows = []
    log_headers = ["Log_ID", "Order_ID", "Action", "Old_Status", "New_Status", "Note", "Created_At", "User"]
    _write_sheet(wb.create_sheet("Activity_Log"), log_headers, log_rows)

    settings_rows = []
    try:
        settings = db.get_settings() or {}
        settings_rows = [{"Key": k, "Value": v} for k, v in settings.items()]
    except Exception:
        pass
    _write_sheet(wb.create_sheet("Settings"), ["Key", "Value"], settings_rows)

    out = BytesIO()
    wb.save(out)
    wb.close()
    out.seek(0)
    return out, len(orders), len(items)


def install_data_export(app, db):
    if getattr(app, "_ezz_data_export_installed", False):
        return
    app._ezz_data_export_installed = True
    auth = app.extensions.get("ezz_auth")
    current_user = auth.get("current_user") if auth else (lambda: None)

    @app.get("/api/data/export-xlsx")
    def export_current_xlsx():
        user = current_user()
        if not user:
            return jsonify({"error": "تسجيل الدخول مطلوب", "authenticated": False}), 401
        try:
            workbook, order_count, item_count = _build_workbook(db)
            ts = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d_%H%M%S")
            response = send_file(
                workbook,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"Ezz_Pharmacy_Backup_{ts}.xlsx",
                max_age=0,
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Export-Orders"] = str(order_count)
            response.headers["X-Export-Items"] = str(item_count)
            return response
        except Exception as exc:
            return jsonify({"error": f"تعذر تصدير البيانات: {exc}"}), 500
