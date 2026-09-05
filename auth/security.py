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

import secrets
from flask import request, session, jsonify

def _get_csrf_token():
    token = str(session.get("csrf_token") or "")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token

def install_csrf(app):
    if getattr(app, "_ezz_csrf_installed", False):
        return
    app._ezz_csrf_installed = True

    @app.context_processor
    def csrf_context():
        return {"csrf_token": _get_csrf_token}

    @app.get("/api/auth/csrf")
    def csrf_api():
        return jsonify({"csrf_token": _get_csrf_token()})

    @app.before_request
    def csrf_protection():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        expected = str(session.get("csrf_token") or "")
        if expected and supplied and hmac.compare_digest(expected, str(supplied)):
            return None
        return jsonify({"error": "رمز الحماية CSRF غير صالح أو مفقود"}), 403
