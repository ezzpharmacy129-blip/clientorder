# Temporary Admin Recovery

This file documents the emergency recovery hook added for the production `admin` account.

It is gated by `ADMIN_RECOVERY_TOKEN` and `ADMIN_RECOVERY_PASSWORD`, only updates the `admin` username, increments `session_version`, and is intended to be removed immediately after successful login verification.

No order, customer, product, backup, or other application data is modified by the recovery SQL statement.
