import logging
import hmac
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from oncall.config import settings

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/slack/events", "/api/health", "/auth/login", "/auth/callback", "/auth/logout", "/auth/logged-out"}

_signer = URLSafeTimedSerializer(settings.session_secret)

SESSION_COOKIE = "oncall_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _get_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)

        user = _get_user(request)
        if user:
            request.state.user = user
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        return RedirectResponse(url="/auth/login")


def _callback_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.hostname)
    return f"{scheme}://{host}/auth/callback"


async def login(request: Request):
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": _callback_url(request),
        "scope": "read:org" if settings.github_allowed_org else "read:user",
        "state": state,
    })
    response = RedirectResponse(url=f"https://github.com/login/oauth/authorize?{params}")
    response.set_cookie("oauth_state", state, httponly=True, max_age=600, samesite="lax")
    return response


async def callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("oauth_state")

    if not code or not state or not stored_state:
        return JSONResponse({"detail": "Missing OAuth parameters"}, status_code=400)

    if not hmac.compare_digest(state, stored_state):
        return JSONResponse({"detail": "Invalid state"}, status_code=400)

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("OAuth token exchange failed: %s", token_data)
            return JSONResponse({"detail": "OAuth token exchange failed", "error": token_data}, status_code=400)

        headers = {"Authorization": f"Bearer {access_token}"}

        user_resp = await client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code != 200:
            logger.error("GitHub user fetch failed: %s %s", user_resp.status_code, user_resp.text)
            return JSONResponse({"detail": "Failed to fetch GitHub user", "status": user_resp.status_code, "body": user_resp.text}, status_code=400)
        user_data = user_resp.json()

        if settings.github_allowed_org:
            orgs_resp = await client.get("https://api.github.com/user/orgs", headers=headers)
            if orgs_resp.status_code != 200:
                return JSONResponse({"detail": "Failed to fetch GitHub orgs"}, status_code=400)
            org_logins = {o["login"] for o in orgs_resp.json()}
            if settings.github_allowed_org not in org_logins:
                return JSONResponse(
                    {"detail": f"Not a member of {settings.github_allowed_org}"},
                    status_code=403,
                )

    session_data = {
        "login": user_data["login"],
        "avatar_url": user_data.get("avatar_url", ""),
    }
    token = _signer.dumps(session_data)

    response = RedirectResponse(url="/")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        max_age=SESSION_MAX_AGE,
        path="/",
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


async def logout(request: Request):  # noqa: ARG001
    response = RedirectResponse(url="/auth/logged-out")
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    return response


async def logged_out(request: Request):  # noqa: ARG001
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Logged out</title>
<style>
body{background:#0a0a0c;color:#e8e8ec;font-family:system-ui;display:flex;
justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{text-align:center}
a{color:#22c55e;text-decoration:none;font-size:0.9rem}
a:hover{text-decoration:underline}
h2{font-size:1.1rem;font-weight:500;margin-bottom:1rem}
</style></head><body><div class="box">
<h2>You have been logged out.</h2>
<a href="/auth/login">Log in again</a>
</div></body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
