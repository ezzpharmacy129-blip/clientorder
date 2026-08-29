# -*- coding: utf-8 -*-
"""One-time operational-data reset for the controlled clean restart."""
import os


def reset_if_requested(db_obj):
    if str(os.environ.get("EZZ_RESET_OPERATIONAL_DATA", "")).strip() != "1":
        return False

    # Create a persistent marker table first so a container restart cannot
    # repeat the destructive operation while the temporary environment flag
    # is still present.
    with db_obj._connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ezz_runtime_flags (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = conn.execute("SELECT value FROM ezz_runtime_flags WHERE key=%s", ("operational_reset_v1",)).fetchone()
        if row and row.get("value") == "done":
            return False

    # CloudDB.reset_all_data creates an automatic cloud backup before clearing
    # operational records and intentionally retains settings/message templates.
    db_obj.reset_all_data()

    with db_obj._connect() as conn:
        conn.execute(
            "INSERT INTO ezz_runtime_flags(key,value) VALUES (%s,%s) "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            ("operational_reset_v1", "done"),
        )
    return True
