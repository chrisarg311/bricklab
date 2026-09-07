"""
Clerk JWT verification for PictoBrick FastAPI endpoints.

Clerk issues RS256-signed JWTs.  We verify them locally against the public
keys published at the Clerk JWKS endpoint — no round-trip to Clerk per request.

JWKS are fetched once and cached for the lifetime of the process.  Clerk rotates
keys infrequently; for production you'd add a TTL and re-fetch on 401, but this
is sufficient for Phase 2.

Required env var (one of):
  CLERK_JWKS_URL  — full URL e.g. https://<domain>/.well-known/jwks.json
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY — Clerk publishable key; JWKS URL is derived
"""
from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache

import httpx
from fastapi import Header, HTTPException
from jose import JWTError, jwt

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWKS URL resolution
# ---------------------------------------------------------------------------

def _derive_jwks_url() -> str:
    """Return the Clerk JWKS URL from env vars."""
    explicit = os.environ.get("CLERK_JWKS_URL", "").strip()
    if explicit:
        return explicit

    pk = os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "").strip()
    if not pk:
        raise RuntimeError(
            "Set CLERK_JWKS_URL or NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY in the environment."
        )

    # pk format: pk_test_<base64>  or  pk_live_<base64>
    # The base64 segment decodes to  <clerk-domain>$
    b64_segment = pk.split("_", 2)[-1]                      # drop "pk_test_" / "pk_live_"
    padding = "=" * (-len(b64_segment) % 4)
    domain = base64.b64decode(b64_segment + padding).decode("utf-8", errors="ignore").rstrip("$")
    url = f"https://{domain}/.well-known/jwks.json"
    log.info("Derived Clerk JWKS URL: %s", url)
    return url


@lru_cache(maxsize=1)
def _fetch_jwks() -> dict:
    """Fetch and cache the Clerk JWKS.  Called once per process lifetime."""
    url = _derive_jwks_url()
    log.info("Fetching Clerk JWKS from %s", url)
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _decode_token(authorization: str) -> str:
    """Verify a Bearer token and return the Clerk user_id (sub claim)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization header must be: Bearer <token>")
    token = authorization[7:].strip()
    try:
        jwks = _fetch_jwks()
        payload = jwt.decode(token, jwks, algorithms=["RS256"])
    except JWTError as exc:
        raise HTTPException(401, f"Invalid token: {exc}") from exc

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Token is missing the 'sub' (user_id) claim")
    return user_id


async def get_current_user_id(authorization: str = Header(default="")) -> str:
    """
    FastAPI dependency — **requires** a valid Clerk JWT.

    Usage::

        @app.get("/api/builds")
        def list_builds(user_id: str = Depends(get_current_user_id)):
            ...
    """
    if not authorization:
        raise HTTPException(401, "Authorization header is required")
    return _decode_token(authorization)


async def get_optional_user_id(authorization: str = Header(default="")) -> str:
    """
    FastAPI dependency — accepts a Clerk JWT but falls back to "anonymous"
    if none is provided.  Used for endpoints that work for both authed and
    unauthed callers (e.g. POST /api/jobs during local dev / testing).
    """
    if not authorization:
        return "anonymous"
    try:
        return _decode_token(authorization)
    except HTTPException:
        # Malformed token — treat as anonymous rather than hard-failing, so
        # the PoC /api/jobs endpoint still works without a token during dev.
        return "anonymous"
