# -*- coding: utf-8 -*-
"""Safe CloudDB order-edit compatibility layer.

Keeps existing item rows when the same product remains in the order, so
images/availability/pricing metadata are not discarded by an ordinary edit.
Creates a real undo snapshot before changing the order.
"""


def install_cloud_order_update_fix(db):
    if db.__class__.__module__ != "cloud_db":
        return
    CloudDB = db.__class__
    if getattr(CloudDB, "_ezz_order_update_fix_v2", False):
        return

    from db import STATUS_PENDING, now_str

    def safe_update_order(self, order_id, fields, products=None, user="موظف"):
        with self._connect() as conn:
            current = self._fetch_order(conn, order_id)
            if not current:
                return None

            snapshot = self._snapshot(conn, order_id)
            updates = dict(fields or {})

            if products is not None:
                clean_products = []
                for p in products:
                    try:
                        qty = int(p.get("quantity", 0))
                    except (TypeError, ValueError):
                        qty = 0
                    name = str(p.get("product_name", "")).strip()
                    if name and qty > 0:
                        clean_products.append({"product_name": name, "quantity": qty})
                if not clean_products:
                    raise ValueError("يجب إضافة منتج واحد على الأقل")

                updates["Product_Name"] = "، ".join(
                    f"{p['product_name']} × {p['quantity']}" for p in clean_products
                )
                updates["Quantity"] = sum(p["quantity"] for p in clean_products)

                existing = self._fetch_items(conn, order_id)
                by_name = {}
                for item in existing:
                    key = str(item.get("Product_Name") or "").strip().casefold()
                    by_name.setdefault(key, []).append(item)

                used = set()
                for p in clean_products:
                    key = p["product_name"].casefold()
                    candidates = by_name.get(key, [])
                    item = next((x for x in candidates if x.get("Item_ID") not in used), None)
                    if item:
                        used.add(item.get("Item_ID"))
                        conn.execute(
                            "UPDATE order_items SET product_name=%s, quantity=%s WHERE item_id=%s",
                            (p["product_name"], p["quantity"], item["Item_ID"]),
                        )
                    else:
                        ts = now_str()
                        conn.execute(
                            "INSERT INTO order_items(item_id,order_id,product_name,quantity,image_path,availability_status,available_price,discounted_price,unavailable_reason,availability_note,price_confirmation_required,available_at,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                self._next_item_id(conn), str(order_id), p["product_name"], p["quantity"], "",
                                STATUS_PENDING, "", "", "", "", "", "", ts,
                            ),
                        )

                for item in existing:
                    if item.get("Item_ID") not in used:
                        conn.execute("DELETE FROM order_items WHERE item_id=%s", (item.get("Item_ID"),))

            col_map = {
                "Customer_Name": "customer_name", "Phone": "phone", "Notes": "notes", "Order_Date": "order_date",
                "Status": "status", "Available_Date": "available_date", "Contact_Status": "contact_status",
                "Last_Contact_Date": "last_contact_date", "Next_Followup_Date": "next_followup_date",
                "Pickup_Date": "pickup_date", "Product_Name": "product_name", "Quantity": "quantity",
            }
            sets, params = [], []
            for key, value in updates.items():
                if key in col_map:
                    sets.append(f"{col_map[key]}=%s")
                    params.append(value)
            if sets:
                sets.append("updated_at=%s")
                params.append(now_str())
                params.append(str(order_id))
                conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE order_id=%s", params)

            new_status = updates.get("Status", current["Status"])
            self._invalidate_undo(conn, order_id)
            self._log(conn, order_id, "تعديل بيانات الطلب", current["Status"], new_status, "تم تعديل بيانات الطلب", user)
            self._add_undo(conn, order_id, "تعديل بيانات الطلب", snapshot, user)
            return self._refresh_order_in_conn(conn, order_id)

    CloudDB.update_order = safe_update_order
    CloudDB._ezz_order_update_fix_v2 = True
