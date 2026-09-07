from pathlib import Path


POLICY = Path("authorization_policy.py").read_text(encoding="utf-8")


def test_admin_root_is_an_admin_boundary():
    assert 'ADMIN_EXACT = {' in POLICY
    assert '("GET", "/admin"),' in POLICY
