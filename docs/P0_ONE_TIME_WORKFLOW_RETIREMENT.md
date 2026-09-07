# P0: Retire one-time users dashboard cleanup workflow

`one-time-users-cleanup.yml` is retired because it can modify `static/app.js` / `static/style.css` and push directly to `main` with `contents: write`.

The workflow is kept only as a disabled manual stub for historical traceability. No source mutation or automatic push remains.
