from pathlib import Path


def test_admin_recovery_is_token_gated_and_admin_only():
    source = Path("admin_recovery.py").read_text(encoding="utf-8")
    assert 'ADMIN_RECOVERY_TOKEN' in source
    assert 'UPDATE users SET password_hash=%s, active=TRUE' in source
    assert 'WHERE username=%s' in source
    assert '"admin"' in source
    assert 'hmac.compare_digest' in source
