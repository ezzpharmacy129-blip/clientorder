# Orders Core — Production Contract

## Production source of truth

Render production uses `DATABASE_URL`, so `db.py` selects the PostgreSQL `CloudDB` implementation. Production order persistence therefore lives in `cloud_db.py`; the Excel implementation in `db.py` remains a legacy/local backend and is not to be deleted until usage is proven absent.

## Request path

```
HTTP route (app.py)
    -> db facade selected at startup
    -> CloudDB method (cloud_db.py)
    -> PostgreSQL transaction
    -> audit / undo where applicable
    -> JSON response
```

## Canonical order operations

| Operation | HTTP entry point | Canonical CloudDB method |
|---|---|---|
| Create | order-create route | `create_order()` |
| Edit fields/items | order update route | `update_order()` |
| Availability | `POST /api/orders/<id>/availability` | `set_availability()` |
| Contact status | `POST /api/orders/<id>/contact-status` | `set_contact_status()` |
| Pickup | `POST /api/orders/<id>/pickup` | `mark_pickup()` |
| Not picked | `POST /api/orders/<id>/not-picked` | `mark_not_picked()` |
| Postpone | `POST /api/orders/<id>/postpone` | `postpone()` |
| Cancel | `POST /api/orders/<id>/cancel` | `cancel_order()` |
| Delete | `DELETE /api/orders/<id>` | `delete_order()` |
| Undo | `POST /api/orders/<id>/undo` | `undo_last()` |
| Item image | image endpoints | `set_item_image()` / `delete_item_image()` |

## Rules

1. Routes validate HTTP input and authorization; they must not implement order business rules.
2. `CloudDB` owns PostgreSQL reads/writes and transactional business operations.
3. Status transitions must use dedicated workflow methods rather than arbitrary `Status` updates.
4. `Item_ID` is the stable identity of an order item.
5. Product edits must preserve item metadata unless an explicit change is requested.
6. Any order mutation that supports Undo must create its snapshot before mutation.
7. Audit actor identity comes from the authenticated user, not a hard-coded employee label.
8. Compatibility endpoints may remain for existing clients, but must delegate to canonical behavior and must not create a second implementation.

## Legacy boundary

`db.py` is classified as **LEGACY / LOCAL BACKEND** for this phase. It remains untouched until repository-wide usage analysis proves it can be retired safely.

## P1.1 scope completed by this document

This establishes the production Order Core contract before any physical module moves. Future P1 work can refactor around this contract without changing business behavior.
