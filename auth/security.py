# -*- coding: utf-8 -*-
"""Shared password primitives for local and PostgreSQL authentication.

New passwords use Argon2id. Existing PBKDF2-SHA256 hashes are still accepted
only for migration; after a successful login the password is re-hashed with
Argon2id and the stored value is replaced.
"""
import base64
import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher()

def hash_password(password):
    password = str(password or "")
    if not password:
        raise ValueError("كلمة المرور مطلوبة")
    return _PASSWORD_HASHER.hash(password)

def _verify_legacy_pbkdf2(password, encoded):
    try:
        method, iterations, salt, digest = str(encoded).split("$", 3)
        if method != "pbkdf2_sha256":
            return False
        dec = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        actual = hashlib.pbkdf2_hmac(
            "sha256", str(password).encode(), dec(salt), int(iterations)
        )
        return hmac.compare_digest(actual, dec(digest))
    except (TypeError, ValueError, UnicodeError):
        return False

def verify_password(password, encoded):
    encoded = str(encoded or "")
    if encoded.startswith("$argon2"):
        try:
            _PASSWORD_HASHER.verify(encoded, str(password or ""))
            return True
        except (VerifyMismatchError, VerificationError, InvalidHash, ValueError):
            return False
    if encoded.startswith("pbkdf2_sha256$"):
        return _verify_legacy_pbkdf2(password, encoded)
    return False

def needs_rehash(encoded):
    encoded = str(encoded or "")
    if not encoded.startswith("$argon2"):
        return True
    try:
        return _PASSWORD_HASHER.check_needs_rehash(encoded)
    except (InvalidHash, ValueError):
        return True
