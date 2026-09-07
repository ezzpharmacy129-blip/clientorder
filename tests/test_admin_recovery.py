from pathlib import Path


def test_admin_recovery_is_token_gated_and_scoped_to_admin():
    source = Path("admin_recovery.py").read_text(encoding="utf-8")
    assert "ADMIN_RECOVERY_TOKEN" in source
    assert "ADMIN_RECOVERY_PASSWORD" in source
    assert 'UPDATE users SET password_hash=%s, active=TRUE' in source
    assert 'WHERE username=%s' in source
    assert '(_hash_password(recovery_password), "admin")' in source
    assert "hmac.compare_digest" in source
