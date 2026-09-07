# P0 workflow cleanup

The following workflows were one-time source-code patchers and are now retired:

- `fix-excel-export.yml`
- `fix-backups-null.yml`
- `repair-backups.yml`
- `integrate-users-dashboard.yml`
- `update-shortage-whatsapp-notes.yml`

They remain available only as manual, read-only stubs (`workflow_dispatch`) for historical traceability. None may modify application source code or push commits to `main`.

The permanent application behavior must live in the repository source tree and be reviewed through normal pull requests.
