import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from httpx import AsyncClient as HTTPAsyncClient
from telethon import TelegramClient
from telethon.events import NewMessage

from shared.schemas import (
    HTTPErrorResponse,
    NotificationById,
    RegistrationResponse,
    User,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


__all__ = ["app", "run"]

BOT_LISTEN = os.environ["BOT_LISTEN"]
BOT_PORT = int(os.environ["BOT_PORT"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_SESSION = os.environ["BOT_SESSION"]
CONTROL_URL = os.environ["CONTROL_URL"]
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
TELEGRAM_API_ID = int(os.environ["TELEGRAM_API_ID"])
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tg_client = TelegramClient(BOT_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH)
http_client = HTTPAsyncClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    await tg_client.connect()
    await tg_client.sign_in(bot_token=TELEGRAM_TOKEN)
    tg_client.on(NewMessage(pattern="/start"))(handle_start)
    loop = asyncio.get_running_loop()
    tg_task = loop.create_task(tg_client.run_until_disconnected())

    yield

    tg_task.cancel()
    await asyncio.gather(tg_task, return_exceptions=True)
    await tg_client.disconnect()
    await http_client.aclose()


header_scheme = APIKeyHeader(name="X-API-Key")


async def verify_token(api_key: Annotated[str, Depends(header_scheme)]) -> None:
    if not secrets.compare_digest(api_key, BOT_TOKEN):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Invalid token")


app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
auth_app = APIRouter(dependencies=[Depends(verify_token)])


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


@auth_app.post("/notification")
async def notify(req: NotificationById) -> Response:
    await tg_client.send_message(req.recipient, req.message)
    return Response(status_code=HTTPStatus.OK)


async def send_registration(req: User) -> RegistrationResponse:
    url = f"{CONTROL_URL}/user"
    headers = {"X-API-Key": CONTROL_TOKEN}
    resp = await http_client.put(url, headers=headers, json=req.model_dump())

    if resp.status_code == HTTPStatus.OK:
        return RegistrationResponse.model_validate(resp.json())

    err = HTTPErrorResponse.model_validate(resp.json())
    raise RuntimeError(err.detail)


async def handle_start(event: NewMessage.Event) -> None:
    sender = await event.get_sender()

    try:
        req = User.from_telegram_user(sender)
        result = await send_registration(req)

    except (ValueError, RuntimeError) as err:
        logger.info(err)
        await event.respond(str(err))
        return

    message = (
        "Your new credentials:\n\n"
        f"**Login:** {req.username}\n"
        f"**Password:** {result.password}\n\n"
        "Our team is currently setting up your access. We will send a confirmation "
        "message as soon as your account is ready to use."
    )

    await event.respond(message)


app.include_router(auth_app)


def run() -> None:
    uvicorn.run(
        "telegram_bot.main:app",
        host=BOT_LISTEN,
        port=BOT_PORT,
        loop="uvloop",
        log_config=None,
    )
