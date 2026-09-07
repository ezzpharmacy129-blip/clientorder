# P1.6 — Permission Matrix

The application has two roles: `employee` and `admin`.

## Effective production contract

| Operation | Employee | Admin | Enforcement |
|---|---:|---:|---|
| Create order | ✅ | ✅ | Authenticated user |
| Edit order | ✅ | ✅ | Authenticated user |
| Availability | ✅ | ✅ | Authenticated user |
| Contact / WhatsApp | ✅ | ✅ | Authenticated user |
| Pickup / Not picked / Postpone | ✅ | ✅ | Authenticated user |
| Cancel | ✅ | ✅ | Authenticated user; workflow rules |
| Delete order | ❌ | ✅ | Central authorization policy + server confirmation |
| Import | ❌ | ✅ | Central authorization policy |
| Restore | ❌ | ✅ | Central authorization policy |
| Reset | ❌ | ✅ | Central authorization policy + server confirmation |
| Manage users | ❌ | ✅ | Central authorization policy (/api/admin/*) |
| Audit viewing | current UI policy | current UI policy | Existing audit endpoint/UI behavior |

## Source of truth

`authorization_policy.py` is the server-side source for the admin boundary.

`auth_pg.py` owns authentication, user identity, password/session handling, and user-management endpoints.

Admin route decorators were removed from `auth_pg.py` because they duplicated the central policy. The existing behavior is preserved by the global `before_request` authorization policy.

No business permission was broadened or reduced by this refactor.

## Safety rule

A frontend button is never considered permission enforcement. The server-side policy must reject unauthorized requests.

## Intentionally unchanged

Message-template permissions, export access, shortage operations, and normal order workflow permissions are unchanged until explicit business rules require a change.
