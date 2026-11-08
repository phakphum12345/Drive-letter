# Research OS Identity Context Gate

## Purpose

Keep Friend bound to the verified Research OS principal and the correct workspace/profile/session. The shared Flutter UI must not choose a user identity by prompt or by an untrusted client-supplied owner field.

## Verified current path

```text
Google / Research OS login
        -> signed Research OS session
        -> /v1/ai/generate
        -> Friend proxy
        -> Owner Friend Service :8790
        -> owner/profile/session scoped memory
```

The signed session contains `user_id`, `email`, `role`, `session_id`, `iat`, and `exp`. `verify_session()` validates the signature, expiry, completeness, and revocation state.

The Owner Friend Service already validates `X-Research-OS-Owner`, `X-Research-OS-Profile`, and `X-Research-OS-Session` before protected operations and passes those scopes into Friend requests and memory recall.

## Implementation added — exact-head verification pending

The canonical API-to-Friend handoff now resolves a trusted `IdentityContext` from `require_session(headers)`:

- `user_id` and `role` are taken only from the verified signed session.
- Friend owner scope is supplied by the server's configured `FRIEND_OWNER_ID`; the client cannot choose it.
- Profile scope is a stable opaque identifier derived from the verified `user_id`.
- Session scope is copied from the verified signed session claim. URL-safe session IDs produced by `secrets.token_urlsafe()` are accepted, including IDs beginning with `_` or `-`.
- Friend proxy headers are generated from this context. Request-body identity keys are removed before forwarding.
- The same identity context is used by Friend generation and the memory-related paths that call the canonical identity resolver.

The Owner Friend Service validates owner/profile/session independently. Its session validator now accepts the URL-safe leading characters that Python's token generator may produce, while owner/profile identifiers retain their stricter validation. The controlled ActionIntent contract applies the same URL-safe rule only to its session field.

Regression coverage includes missing/non-owner session rejection, client identity override resistance, same-user session continuity, cross-user separation, URL-safe leading session characters, and owner/profile/session-scoped preview authorization.

**Verification status:** implementation and regression tests are committed on the PR branch. Do not mark this gate complete until all exact-head API, Friend, Windows installer, and final-gate checks pass. CI evidence does not replace a separate read-only check of the user's actual Windows service host.

## Required invariant

> Friend must be placed with the correct person, system/workspace, and data.

For the shared Research OS UI, the canonical flow must be:

```text
Verified Research OS session
        |
        +--> principal.user_id
        +--> principal.role
        +--> session_id
        |
        v
Trusted identity context
        |
        +--> Friend owner/workspace/profile binding
        +--> Memory scope
        +--> Knowledge scope
        +--> Tool authorization
```

A client-supplied identity field must never override the verified session principal.

## Acceptance criteria

1. Friend requests with no valid Research OS session are rejected when the Friend route requires identity.
2. A valid session determines the effective user context server-side.
3. Client-supplied owner/profile/session identity cannot cross the verified session boundary.
4. Memory recall and writes use the same effective identity context as Friend.
5. Different users cannot read or write another user's Friend memory/workspace through the canonical API.
6. Existing Owner Special loopback protection remains intact.
7. Existing app branding remains canonical: `apps/research_os_flutter/assets/branding/research_os_master.webp` -> Windows `runner/resources/app_icon.ico`.
8. Flutter, Windows EXE identity, installer, and E2E gates remain green after the change.
