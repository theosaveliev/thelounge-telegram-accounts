import asyncio
import logging
import os
import secrets
import time
from http import HTTPStatus
from typing import TYPE_CHECKING

import httpx
import uvicorn
import uvloop
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from telethon import TelegramClient, events

from shared.schemas import (
    HTTPErrorResponse,
    RegistrationResponse,
    TelegramNotification,
    TelegramRegistration,
)

if TYPE_CHECKING:
    from telethon.events import NewMessage

TELEGRAM_API_ID = int(os.environ["TELEGRAM_API_ID"])
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BOT_SESSION = os.environ["BOT_SESSION"]
BOT_LISTEN = os.environ["BOT_LISTEN"]
BOT_PORT = int(os.environ["BOT_PORT"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
CONTROL_URL = os.environ["CONTROL_URL"]
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(docs_url=None, redoc_url=None)
tg_client = TelegramClient(BOT_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH)
http_client = httpx.AsyncClient()


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


@app.post("/notify")
async def notify(req: TelegramNotification) -> Response:
    if not secrets.compare_digest(req.token, BOT_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    ts = int(time.time())
    log = {"api": "/notify", "id": req.id, "timestamp": ts}
    logger.info(log)

    await tg_client.send_message(req.id, req.message)
    return Response(status_code=HTTPStatus.OK)


async def register_user(event: NewMessage.Event) -> None:
    sender = await event.get_sender()
    url = f"{CONTROL_URL}/register"
    assert sender.username is not None  # noqa: S101  # validated in validate_sender()

    req = TelegramRegistration(
        id=sender.id, username=sender.username, token=CONTROL_TOKEN
    )

    resp = await http_client.post(url, json=req.model_dump())

    if resp.status_code == HTTPStatus.CREATED:
        ok = RegistrationResponse.model_validate(resp.json())
        message = (
            "**Welcome aboard!**\n"
            "Please save the credentials:\n\n"
            f"**Login:** {sender.username}\n"
            f"**Password:** {ok.password}\n\n"
            "Our team is currently setting up your access. "
            "We will send a confirmation message as soon as "
            "your account is ready to use."
        )
        await event.respond(message)

    else:
        err = HTTPErrorResponse.model_validate(resp.json())
        await event.respond(err.detail)
        raise RuntimeError(err.detail)


FORBIDDEN = {
    "restricted": (
        "**Access denied:** your Telegram account currently has active restrictions."
    ),
    "scam": (
        "**Access denied:** this account has been flagged for suspicious activity."
    ),
    "fake": (
        "**Access denied:** this account appears to be impersonating another user."
    ),
    "bot": ("**Access denied:** no bots allowed."),
}


async def validate_sender(event: NewMessage.Event) -> None:
    sender = await event.get_sender()
    for attr, message in FORBIDDEN.items():
        if getattr(sender, attr, None):
            await event.respond(message)
            raise ValueError(message)

    if not isinstance(sender.username, str):
        message = (
            "A @username is required. Please update your profile and send /start again."
        )
        await event.respond(message)
        raise ValueError(message)


async def handle_start(event: NewMessage.Event) -> None:
    await validate_sender(event)
    await register_user(event)


async def main() -> None:
    await tg_client.connect()
    await tg_client.sign_in(bot_token=TELEGRAM_TOKEN)
    tg_client.on(events.NewMessage(pattern="/start"))(handle_start)

    config = uvicorn.Config(
        app, host=BOT_LISTEN, port=BOT_PORT, loop="none", log_config=None
    )
    server = uvicorn.Server(config)
    logger.info("Bot is running...")

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(tg_client.run_until_disconnected())
            tg.create_task(server.serve())

    except* KeyboardInterrupt, asyncio.CancelledError:
        logger.info("Shutting down...")

    finally:
        await tg_client.disconnect()
        await http_client.aclose()


def run() -> None:
    asyncio.run(main(), loop_factory=uvloop.new_event_loop)
