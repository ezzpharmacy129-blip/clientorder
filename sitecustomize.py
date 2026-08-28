# -*- coding: utf-8 -*-
"""Load the current database-backed authentication before Flask creates app:app."""

import flask

_original_init = flask.Flask.__init__


def _protected_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    try:
        from auth_bootstrap import install_auth
        # app.py has already imported db before constructing Flask, so obtain it lazily here.
        from db import db
        install_auth(self, db)
    except Exception:
        # Do not hide the real application startup error; production configuration is validated by auth_bootstrap.
        raise


if not getattr(flask.Flask, "_ezz_auth_constructor_patched_v2", False):
    flask.Flask.__init__ = _protected_init
    flask.Flask._ezz_auth_constructor_patched_v2 = True
