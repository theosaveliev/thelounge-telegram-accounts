import asyncio
import logging
import os
import re
import secrets
import string
from typing import TYPE_CHECKING

from docker import DockerClient
from telethon import TelegramClient, events

if TYPE_CHECKING:
    from telethon.events import NewMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def exec_in_container(container_name: str, command: list[str]) -> bool:
    client = DockerClient(base_url="unix:///var/run/docker.sock")
    container = client.containers.get(container_name)
    exit_code, output = container.exec_run(command, stream=False, user="1000:1000")
    assert isinstance(output, bytes)  # noqa: S101
    decoded = output.decode()
    logger.info(decoded)
    return exit_code == 0 and "[ERROR]" not in decoded


def generate_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
        ):
            return pw


async def set_password(event: NewMessage.Event) -> None:
    loop = asyncio.get_event_loop()
    pw = await loop.run_in_executor(None, generate_password, 20)

    sender = await event.get_sender()
    assert sender.username is not None  # noqa: S101
    cmd: list[str] = ["thelounge", "add", sender.username, "--password", pw]

    req_info = {"id": sender.id, "username": sender.username, "password": pw}
    logger.info(req_info)

    created = await loop.run_in_executor(None, exec_in_container, "thelounge", cmd)
    if not created:
        await event.respond("User already exists.")
        raise RuntimeError(req_info)

    message = f"**Login:** {sender.username}\n**Password:** {pw}\n\n**Welcome aboard!**"
    await event.respond(message)


FORBIDDEN = {
    "restricted": "The telegram account is restricted.",
    "scam": "The telegram account is marked with scam.",
    "fake": "The telegram account is fake.",
    "bot": "No bots allowed.",
}

USERNAME_REGEX = re.compile(r"[a-zA-Z0-9_]+")


async def validate_sender(event: NewMessage.Event) -> None:
    sender = await event.get_sender()
    for attr, message in FORBIDDEN.items():
        if getattr(sender, attr, None):
            await event.respond(message)
            raise ValueError(message)

    if not isinstance(sender.username, str):
        message = "Please set @username for your Telegram account."
        await event.respond(message)
        raise ValueError(message)

    if USERNAME_REGEX.fullmatch(sender.username) is None:
        message = "Invalid @username."
        await event.respond(message)
        raise ValueError(message)


async def handle_start(event: NewMessage.Event) -> None:
    await validate_sender(event)
    await set_password(event)


async def health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read(1024)
    writer.write(b"HTTP/1.1 200 OK\r\n\r\n")
    writer.close()


async def amain() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

    client = TelegramClient("data/bot", api_id, api_hash)
    await client.connect()
    await client.sign_in(bot_token=bot_token)

    client.on(events.NewMessage(pattern="/start"))(handle_start)
    logger.info("Bot is running...")

    hh = await asyncio.start_server(health, "", 8080)
    async with hh:
        try:
            await client.run_until_disconnected()

        except KeyboardInterrupt, asyncio.CancelledError:
            logger.info("Shutting down...")

        finally:
            await client.disconnect()


def main() -> None:
    asyncio.run(amain())
