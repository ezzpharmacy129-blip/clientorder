# -*- coding: utf-8 -*-
"""Load the current database-backed authentication before Flask creates app:app."""
import flask

_original_init = flask.Flask.__init__


def _protected_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    from auth_bootstrap import install_auth
    from auth_security_extensions import install_security_extensions
    from db import db
    install_auth(self, db)
    install_security_extensions(self, db)


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v2", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v2 = True
