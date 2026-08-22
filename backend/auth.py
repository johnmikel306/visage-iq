"""Clerk auth middleware. CLERK_SECRET_KEY empty => auth disabled (dev mode,
actor 'dev@local'). Accepts Authorization: Bearer or Clerk's __session cookie
(the cookie is what lets <img src="/api/image/..."> authenticate)."""
import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import settings

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/health"}
DEV_ACTOR = "dev@local"

_clerk = None


def _client():
    global _clerk
    if _clerk is None:
        from clerk_backend_api import Clerk

        _clerk = Clerk(bearer_auth=settings.clerk_secret_key)
    return _clerk


def domain_ok(email: str | None, domain: str) -> bool:
    if not email:
        return False
    return email.strip().lower().endswith("@" + domain.lower())


async def _verify(request: Request) -> tuple[str | None, JSONResponse | None]:
    """Returns (email, error_response); error None => authenticated. On domain
    rejection both are set so the caller can audit."""
    from clerk_backend_api.security.types import AuthenticateRequestOptions

    hx = httpx.Request(request.method, str(request.url), headers=request.headers.raw)
    state = await _client().authenticate_request_async(hx, AuthenticateRequestOptions())
    if not state.is_signed_in:
        return None, JSONResponse(status_code=401, content={"detail": "Not signed in"})
    email = (state.payload or {}).get("email")
    if not email:
        return None, JSONResponse(
            status_code=401,
            content={"detail": "Session token has no email claim — add {{user.primary_email_address}} as 'email' in Clerk dashboard → Sessions → Customize session token"},
        )
    if not domain_ok(email, settings.allowed_email_domain):
        return email, JSONResponse(status_code=403, content={"detail": "Account domain not allowed"})
    return email, None


async def clerk_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    if not settings.clerk_secret_key:
        request.state.actor = DEV_ACTOR
        return await call_next(request)
    try:
        email, error = await _verify(request)
    except Exception:
        logger.exception("clerk verification error")
        return JSONResponse(status_code=401, content={"detail": "Auth verification failed"})
    if error is not None:
        if error.status_code == 403:
            from backend import audit

            audit.record(email, "auth_denied", details={"status": 403})
        return error
    request.state.actor = email
    return await call_next(request)


def actor_of(request: Request) -> str:
    return getattr(request.state, "actor", DEV_ACTOR)
