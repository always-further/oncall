import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from oncall.auth import AuthMiddleware, callback, login, logout
from oncall.config import settings
from oncall.routes import router

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

app = FastAPI(title="Oncall Shift Tracker")
app.add_middleware(AuthMiddleware)
app.include_router(router)

templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "frontend" / "static")),
    name="static",
)

app.add_api_route("/auth/login", login, methods=["GET"])
app.add_api_route("/auth/callback", callback, methods=["GET"], name="auth_callback")
app.add_api_route("/auth/logout", logout, methods=["GET"])


_slack_handler = None


def _get_slack_handler():
    global _slack_handler
    if _slack_handler is None:
        from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
        from slack_bolt.async_app import AsyncApp
        from oncall.slack_handlers import register_commands

        slack_app = AsyncApp(
            token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )
        register_commands(slack_app)
        _slack_handler = AsyncSlackRequestHandler(slack_app)
    return _slack_handler


@app.post("/slack/events")
async def slack_events(req: Request):
    return await _get_slack_handler().handle(req)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
