# -*- coding: utf-8 -*-
"""Allow an order to be explicitly reset to 'بانتظار التوفر'.

The existing data layer handled pending status per item but rejected saving when
all items were pending. This small compatibility patch fixes only that case and
leaves all other availability validation/behaviour unchanged.
"""

def install_pending_availability_fix(db):
    if getattr(db, "_ezz_pending_availability_fix", False):
        return
    original = db.set_availability
    if getattr(original, "_ezz_pending_wrapper", False):
        db._ezz_pending_availability_fix = True
        return

    from db import _lock, _make_backup, _format_sheet, _atomic_save, today_str, STATUS_PENDING, CONTACT_NOT_CONTACTED

    def patched(order_id, item_updates, available_date=None, user="موظف"):
        updates = item_updates or []
        if not isinstance(updates, list) or not updates:
            return {"error": "أرسل حالة توفر المنتجات", "code": 400}

        # Only intercept the explicit all-pending transition.
        statuses = [str(x.get("availability_status") or "").strip() for x in updates if isinstance(x, dict)]
        if statuses and all(s == "بانتظار التوفر" for s in statuses):
            with _lock:
                wb = db._load()
                if "Orders" not in wb.sheetnames or "Order_Items" not in wb.sheetnames:
                    wb.close()
                    return {"error": "ملف البيانات غير صالح", "code": 500}
                ws = wb["Orders"]
                wi = wb["Order_Items"]
                wl = wb["Activity_Log"]
                wu = wb["Undo_History"]
                old = db._status(ws, order_id)
                if old is None:
                    wb.close()
                    return {"error": "الطلب غير موجود", "code": 404}
                snapshot = db._row_snapshot(ws, wi, order_id)
                if not snapshot or not snapshot.get("items"):
                    wb.close()
                    return {"error": "لا توجد منتجات في هذا الطلب", "code": 409}

                _make_backup()
                db._invalidate_undo(wu, order_id)

                # Reset every product to waiting for supply and clear availability-only fields.
                for row in wi.iter_rows(min_row=2):
                    if str(row[1].value or "") != str(order_id):
                        continue
                    row[5].value = "بانتظار التوفر"
                    row[6].value = ""
                    row[7].value = ""
                    row[8].value = ""
                    row[9].value = ""
                    row[10].value = ""
                    row[11].value = ""

                db._update_fields(ws, order_id, {
                    "Status": STATUS_PENDING,
                    "Available_Date": "",
                    "Contact_Status": CONTACT_NOT_CONTACTED,
                    "Last_Contact_Date": "",
                    "Next_Followup_Date": "",
                    "Pickup_Date": "",
                })
                db._append_log(wl, order_id, "تحديث توفر المنتجات", old, STATUS_PENDING, "تم إرجاع الطلب إلى بانتظار التوفر", user)
                db._add_undo(wu, order_id, "تحديث توفر المنتجات", snapshot, user)
                _format_sheet(ws); _format_sheet(wi); _format_sheet(wl); _format_sheet(wu)
                _atomic_save(wb)
                try:
                    _make_backup("auto")
                except Exception:
                    pass
                return {"order": db.get_order(order_id)}

        return original(order_id, item_updates, available_date, user)

    patched._ezz_pending_wrapper = True
    db.set_availability = patched
    db._ezz_pending_availability_fix = True
