import logging
import os
import secrets
import time
from http import HTTPStatus

import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from control.functions import (
    create_accounts,
    create_filebrowser_users_json,
    create_thelounge_user_files,
    generate_password,
    list_all_users_pending,
    notify_filebrowser_users,
    notify_thelounge_users,
)
from shared.schemas import (
    AuthenticatedRequest,
    RegistrationResponse,
    TelegramRegistration,
)

CONTROL_LISTEN = os.environ["CONTROL_LISTEN"]
CONTROL_PORT = int(os.environ["CONTROL_PORT"])
CONTROL_USERS_DB = os.environ["CONTROL_USERS_DB"]
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(docs_url=None, redoc_url=None)
engine = create_async_engine(f"sqlite+aiosqlite:///{CONTROL_USERS_DB}")
Session = async_sessionmaker(engine)
http_client = httpx.AsyncClient()


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


@app.post("/register")
async def register(req: TelegramRegistration) -> JSONResponse:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    ts = int(time.time())
    log = {"api": "/register", "id": req.id, "username": req.username, "timestamp": ts}
    logger.info(log)
    pw = generate_password(length=20)

    try:
        await create_accounts(
            sessionmaker=Session, request=req, password=pw, timestamp=ts
        )

    except IntegrityError:
        err_text = (
            "It looks like you're already registered! "
            "Please reach back out to the member who "
            "shared this link with you to continue."
        )
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=err_text) from None

    ok = RegistrationResponse(password=pw).model_dump()
    return JSONResponse(status_code=HTTPStatus.CREATED, content=ok)


@app.post("/create_thelounge_user_files")
async def create_thelounge_files(req: AuthenticatedRequest) -> Response:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    await create_thelounge_user_files(sessionmaker=Session)
    return Response(status_code=HTTPStatus.CREATED)


@app.post("/notify_thelounge_users")
async def notify_tl_users(req: AuthenticatedRequest) -> Response:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    await notify_thelounge_users(sessionmaker=Session, http_client=http_client)
    return Response(status_code=HTTPStatus.CREATED)


@app.post("/create_filebrowser_users_json")
async def create_fb_users_json(req: AuthenticatedRequest) -> Response:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    await create_filebrowser_users_json(sessionmaker=Session)
    return Response(status_code=HTTPStatus.CREATED)


@app.post("/notify_filebrowser_users")
async def notify_fb_users(req: AuthenticatedRequest) -> Response:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    await notify_filebrowser_users(sessionmaker=Session, http_client=http_client)
    return Response(status_code=HTTPStatus.CREATED)


@app.post("/list_users_pending")
async def list_users_waiting(req: AuthenticatedRequest) -> JSONResponse:
    if not secrets.compare_digest(req.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    result = await list_all_users_pending(sessionmaker=Session)
    return JSONResponse(status_code=HTTPStatus.OK, content=result)


def run() -> None:
    conf = Config("alembic.ini")
    command.upgrade(conf, "head")
    uvicorn.run(
        "control.main:app",
        host=CONTROL_LISTEN,
        port=CONTROL_PORT,
        loop="uvloop",
        log_config=None,
    )
