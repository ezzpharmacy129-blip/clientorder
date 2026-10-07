# Safe order and shortage correction

Order details and the orders list now open an independent correction form. Existing
products keep `Item_ID`; new products omit it. Explicit removals are submitted only
on save through `deleted_item_ids`. The form never submits workflow or image fields.
The existing PUT, audit and undo implementations remain authoritative.

Pharmacy shortages reuse their existing form and PUT endpoint, with distinct add/edit
titles and submit labels. Customer shortages open the original order editor. All
pharmacy rows, including supplied rows, are reachable in the all filter. Asset
versions were updated. Mobile orders previously inherited a 1040px minimum width;
the correction removes that minimum on mobile so action buttons remain reachable.

Local Excel updates previously replaced all item rows and lacked the deletion
argument. They now update by ID, validate before saving, take the existing undo
snapshot, and preserve metadata. Local undo restores rows by ID. CloudDB also
validates explicit deletions when the products field is omitted.

## Validation

- `python -m unittest discover -s tests -p test_edit_regression.py -v`: 20 passed.
- Cases 1–7 run against real CloudDB methods with an in-memory SQLite adapter and
  a temporary Excel backend: customer fields, metadata, additions, explicit
  deletions, empty-order rejection, workflow preservation, undo and actor identity.
- Cases 8–10 cover pharmacy editing/undo and frontend entry points. Additional
  checks cover invalid IDs and the real HTTP route with employee permission/CSRF.
- `python tests/edit_ui_browser.py`: passed at 1440px and 390px, using actual
  templates/assets and intercepted synthetic APIs. Covers cancellation, retry,
  item IDs, refreshes, all shortage filters, customer routing and viewport bounds.
  Requires Playwright and its Chromium browser; no live service is accessed.
- JavaScript syntax checks and `node tests/test_customer_reply.cjs`: passed.
- Full unittest discovery retains 15 failures also reproduced on unmodified
  upstream `a0a494efc7573c506e18569620cbe3ba32da2bd8`. These are existing dashboard
  source-contract and legacy CSS-loader expectations. No existing tests were disabled.
- Two existing PostgreSQL integration classes skip without `DATABASE_URL`.
  Offline SQL tests do not verify PostgreSQL-specific locking/types.
- The browser records the existing `cancelled_orders.js` startup reference to
  missing `dashboardFilterOrders`; all tested edit interactions are error-free.

No migration, production data changes, credential changes, image cleanup, reset,
import, restore, or deployment is part of this change.
