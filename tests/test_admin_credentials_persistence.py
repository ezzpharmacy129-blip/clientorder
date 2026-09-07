from pathlib import Path


def test_admin_env_credentials_are_seed_only():
    source = Path(__file__).resolve().parents[1].joinpath("auth_pg.py").read_text(encoding="utf-8")
    marker = 'def ensure_pg_users():'
    start = source.index(marker)
    end = source.index('def migrate_legacy_sqlite():', start)
    block = source[start:end]

    assert "ON CONFLICT(username) DO NOTHING" in block
    assert "password_hash=EXCLUDED.password_hash" not in block
    assert "role='admin',\n                        active=TRUE" not in block
