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
    from fastapi.responses import HTMLResponse

    if "start" not in request.query_params:
        html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>oncall // login</title>
<style>
body{background:#ffffff;color:#212529;font-family:'SF Pro Display',-apple-system,system-ui,sans-serif;
display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{text-align:center}
h1{font-family:'SF Mono',monospace;font-size:1.4rem;font-weight:700;letter-spacing:-0.03em;margin-bottom:0.5rem}
h1 span{color:#16a34a}
p{color:#868e96;font-size:0.85rem;margin-bottom:2rem}
a.btn{display:inline-flex;align-items:center;gap:0.6rem;background:#212529;color:#fff;
text-decoration:none;padding:0.65rem 1.5rem;border-radius:6px;font-size:0.85rem;font-weight:600;
transition:background 0.15s}
a.btn:hover{background:#000}
a.btn svg{width:20px;height:20px}
</style></head><body><div class="box">
<h1><span>//</span> oncall</h1>
<p>Oncall shift tracker</p>
<a class="btn" href="/auth/login?start=1">
<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
Log in with GitHub
</a>
</div></body></html>"""
        return HTMLResponse(content=html)

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
        secure=True,
        max_age=SESSION_MAX_AGE,
        path="/",
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


async def logout(request: Request):  # noqa: ARG001
    response = RedirectResponse(url="/auth/logged-out")
    response.set_cookie(SESSION_COOKIE, "", max_age=0, path="/", httponly=True)
    response.set_cookie(SESSION_COOKIE, "", max_age=0, path="/", httponly=True, secure=True)
    return response


async def logged_out(request: Request):  # noqa: ARG001
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Logged out</title>
<style>
body{background:#ffffff;color:#212529;font-family:system-ui;display:flex;
justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{text-align:center}
a{color:#16a34a;text-decoration:none;font-size:0.9rem}
a:hover{text-decoration:underline}
h2{font-size:1.1rem;font-weight:500;margin-bottom:1rem}
</style></head><body><div class="box">
<h2>You have been logged out.</h2>
<a href="/auth/login">Log in again</a>
</div></body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
