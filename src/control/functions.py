import asyncio
import os
import secrets
import string
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import bcrypt
from sqlalchemy import select

from shared.schemas import TelegramNotification

from .models import (
    ServiceAccountMixin,
    SFTPGoAccount,
    TelegramAccount,
    TheloungeAccount,
)
from .sftpgo_schemas import SFTPGoAdmin, SFTPGoBackup, SFTPGoUser
from .thelounge_schemas import BrowserInfo, NetworkConfig, UserConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    ASM = async_sessionmaker[AsyncSession]
    from httpx import AsyncClient

    from shared.schemas import TelegramRegistration

__all__ = [
    "create_accounts",
    "create_sftpgo_backup_json",
    "create_thelounge_user_files",
    "generate_password",
    "list_all_users_pending",
    "notify_thelounge_users",
]

BOT_URL = os.environ["BOT_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
IRC_NAME = os.environ["IRC_NAME"]
IRC_HOST = os.environ["IRC_HOST"]
IRC_PORT = int(os.environ["IRC_PORT"])
IRC_PASSWORD = os.environ["IRC_PASSWORD"]
THELOUNGE_USERS_DIR = Path(os.environ["THELOUNGE_USERS_DIR"])
SFTPGO_ADMIN = os.environ["SFTPGO_ADMIN"]
SFTPGO_DATA_DIR = os.environ["SFTPGO_DATA_DIR"]
SFTPGO_BACKUP_DIR = Path(os.environ["SFTPGO_BACKUP_DIR"])


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


def encode(data: str) -> bytes:
    return data.encode(encoding="utf-8", errors="strict")


def decode(data: bytes) -> str:
    return data.decode(encoding="utf-8", errors="strict")


def hash_bcrypt(password: str, rounds: int) -> str:
    salt = bcrypt.gensalt(rounds=rounds, prefix=b"2a")
    return decode(bcrypt.hashpw(password=encode(password), salt=salt))


async def create_accounts(
    sessionmaker: ASM, request: TelegramRegistration, password: str, timestamp: int
) -> None:
    pw_tl = hash_bcrypt(password, rounds=11)
    pw_sftp = hash_bcrypt(password, rounds=10)

    tg_acc = TelegramAccount(
        id=request.id, username=request.username, updated=timestamp, meta=""
    )

    tl_acc = TheloungeAccount(
        id=request.id,
        username=request.username,
        password=pw_tl,
        notified=False,
        updated=timestamp,
    )

    sftp_acc = SFTPGoAccount(
        id=request.id,
        username=request.username,
        password=pw_sftp,
        notified=False,
        updated=timestamp,
    )

    async with sessionmaker() as session:
        session.add_all([tg_acc, tl_acc, sftp_acc])
        await session.commit()


def create_thelounge_user_config(username: str, password: str) -> UserConfig:
    browser = BrowserInfo(isSecure=True)
    network = NetworkConfig(
        nick=username,
        name=IRC_NAME,
        host=IRC_HOST,
        port=IRC_PORT,
        tls=True,
        userDisconnected=False,
        rejectUnauthorized=True,
        password=IRC_PASSWORD,
        awayMessage="",
        commands=[],
        username=username,
        realname=username,
        leaveMessage="",
        sasl="",
        saslAccount="",
        saslPassword="",
        channels=[],
        proxyHost="",
        proxyPort=1080,
        proxyUsername="",
        proxyPassword="",
        proxyEnabled=False,
        ignoreList=[],
    )

    return UserConfig(
        log=False,
        password=password,
        sessions={},
        clientSettings={},
        networks=[network],
        browser=browser,
    )


async def create_thelounge_user_files(sessionmaker: ASM) -> None:
    loop = asyncio.get_running_loop()
    async with sessionmaker() as session:
        query = select(TheloungeAccount).where(TheloungeAccount.notified.is_(False))
        result = await session.stream(query)
        async for account in result.scalars():
            config = create_thelounge_user_config(account.username, account.password)
            config_json = config.model_dump_json(exclude_none=True, indent=4)
            user_file = THELOUNGE_USERS_DIR / f"{account.username}.json"

            def write_file(uf: Path = user_file, cj: str = config_json) -> None:
                uf.write_text(cj, encoding="utf-8")

            await loop.run_in_executor(None, write_file)


async def notify_thelounge_users(sessionmaker: ASM, http_client: AsyncClient) -> None:
    url = f"{BOT_URL}/notify"
    async with sessionmaker() as session:
        query = select(TheloungeAccount).where(TheloungeAccount.notified.is_(False))
        result = await session.stream(query)
        accounts: list[TheloungeAccount] = []
        async for account in result.scalars():
            notification = TelegramNotification(
                token=BOT_TOKEN, id=account.id, message="Your IRC account is ready."
            )

            resp = await http_client.post(url, json=notification.model_dump())
            if resp.status_code == HTTPStatus.OK:
                accounts.append(account)

        for account in accounts:
            account.notified = True

        await session.commit()


def create_sftpgo_user(username: str, password: str) -> SFTPGoUser:
    if username == SFTPGO_ADMIN:
        home = SFTPGO_DATA_DIR
    else:
        home = f"{SFTPGO_DATA_DIR}/users/{username}"

    return SFTPGoUser(username=username, password=password, home_dir=home)


async def create_sftpgo_backup_json(sessionmaker: ASM) -> None:
    loop = asyncio.get_running_loop()
    async with sessionmaker() as session:
        users: list[SFTPGoUser] = []
        uquery = select(SFTPGoAccount)
        ures = await session.stream(uquery)
        async for uacc in ures.scalars():
            user = create_sftpgo_user(username=uacc.username, password=uacc.password)
            users.append(user)

        admins: list[SFTPGoAdmin] = []
        aquery = select(SFTPGoAccount).where(SFTPGoAccount.username == SFTPGO_ADMIN)
        ares = await session.execute(aquery)
        aacc = ares.scalar_one_or_none()
        if aacc is not None:
            admin = SFTPGoAdmin(username=aacc.username, password=aacc.password)
            admins.append(admin)

        backup = SFTPGoBackup(users=users, admins=admins)
        backup_json = backup.model_dump_json(exclude_none=True, indent=4)
        backup_file = SFTPGO_BACKUP_DIR / "backup.json"

        def write_file(bfile: Path = backup_file, bjson: str = backup_json) -> None:
            bfile.write_text(bjson, encoding="utf-8")

        await loop.run_in_executor(None, write_file)


async def notify_sftpgo_users(sessionmaker: ASM, http_client: AsyncClient) -> None:
    url = f"{BOT_URL}/notify"
    async with sessionmaker() as session:
        query = select(SFTPGoAccount).where(SFTPGoAccount.notified.is_(False))
        result = await session.stream(query)
        accounts: list[SFTPGoAccount] = []
        async for account in result.scalars():
            notification = TelegramNotification(
                token=BOT_TOKEN, id=account.id, message="Your SFTPGo account is ready."
            )

            resp = await http_client.post(url, json=notification.model_dump())
            if resp.status_code == HTTPStatus.OK:
                accounts.append(account)

        for account in accounts:
            account.notified = True

        await session.commit()


type UserInfo = list[tuple[str, str]]


async def list_users_pending(
    sessionmaker: ASM, model: type[ServiceAccountMixin]
) -> UserInfo:
    async with sessionmaker() as session:
        query = select(model).where(model.notified.is_(False)).order_by(model.username)
        result = await session.scalars(query)
        ret: UserInfo = []
        for account in result.all():
            ts = datetime.fromtimestamp(account.updated).strftime("%d.%m.%Y %H:%M")
            ret.append((account.username, ts))

        return ret


async def list_all_users_pending(sessionmaker: ASM) -> dict[str, UserInfo]:
    thelounge = await list_users_pending(sessionmaker, TheloungeAccount)
    sftpgo = await list_users_pending(sessionmaker, SFTPGoAccount)
    return {"thelounge": thelounge, "sftpgo": sftpgo}
