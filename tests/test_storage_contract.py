# Storage contract check
from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]

def class_methods(path, class_name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("__")}
    raise AssertionError(f"{class_name} not found in {path}")

local = class_methods("db.py", "ExcelDB")
cloud = class_methods("cloud_db.py", "CloudDB")

required = {
    "get_all_orders", "get_order", "get_activity_log", "get_settings", "update_settings",
    "create_order", "update_order", "undo_last", "set_availability", "mark_available",
    "mark_contacted", "set_contact_status", "mark_pickup", "postpone", "cancel_order",
    "delete_order", "set_item_image", "delete_item_image", "reset_all_data",
    "storage_info", "import_legacy_data", "list_backups", "create_manual_backup", "restore_backup"
}

missing_local = sorted(required - local)
missing_cloud = sorted(required - cloud)
assert not missing_local, f"ExcelDB missing: {missing_local}"
assert not missing_cloud, f"CloudDB missing: {missing_cloud}"

text = (ROOT / "db.py").read_text(encoding="utf-8")
assert "if os.environ.get(\"DATABASE_URL\", \"\").strip():" in text
assert "db = CloudDB()" in text
assert "db = ExcelDB()" in text

print(f"STORAGE CONTRACT OK: {len(required)} shared public operations")
