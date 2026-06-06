import asyncio
import logging
import os
import secrets
from http import HTTPStatus
from typing import TYPE_CHECKING

import httpx
import uvicorn
import uvloop
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from telethon import TelegramClient, events

from shared.protocols import LogContext
from shared.schemas import HTTPErrorResponse, NotifById, RegRequest, RegResponse

if TYPE_CHECKING:
    from telethon.events import NewMessage


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
app = FastAPI(docs_url=None, redoc_url=None)
tg_client = TelegramClient(BOT_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH)
http_client = httpx.AsyncClient()


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


@app.post("/notify")
async def notify(req: NotifById) -> Response:
    if not secrets.compare_digest(req.token, BOT_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")

    log = LogContext("/notify", id=req.id, timestamp=req.timestamp)
    logger.info(log)

    await tg_client.send_message(req.id, req.message)
    return Response(status_code=HTTPStatus.CREATED)


type ControlResponse = RegResponse | HTTPErrorResponse


async def send_registration(req: RegRequest) -> ControlResponse:
    resp = await http_client.post(f"{CONTROL_URL}/register_user", json=req.model_dump())

    if resp.status_code == HTTPStatus.CREATED:
        return RegResponse.model_validate(resp.json())

    return HTTPErrorResponse.model_validate(resp.json())


async def register_user(event: NewMessage.Event) -> None:
    sender = await event.get_sender()
    req = RegRequest.from_telegram_user(user=sender, token=CONTROL_TOKEN)

    log = LogContext("/register_user", id=req.id, timestamp=req.timestamp)
    logger.info(log)

    result = await send_registration(req)

    if isinstance(result, HTTPErrorResponse):
        await event.respond(result.detail)
        raise RuntimeError(result.detail)

    message = (
        "**Welcome aboard!**\nPlease save the credentials:\n\n"
        f"**Login:** {sender.username}\n"
        f"**Password:** {result.password}\n\n"
        "Our team is currently setting up your access. We will send a confirmation "
        "message as soon as your account is ready to use."
    )

    await event.respond(message)


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
    log = LogContext("bot_main", state="Running")
    logger.info(log)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(tg_client.run_until_disconnected())
            tg.create_task(server.serve())

    except* KeyboardInterrupt, asyncio.CancelledError:
        log["state"] = "Shutting down"
        logger.info(log)

    finally:
        await tg_client.disconnect()
        await http_client.aclose()


def run() -> None:
    asyncio.run(main(), loop_factory=uvloop.new_event_loop)
