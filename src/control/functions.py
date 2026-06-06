import asyncio
import logging
import os
import secrets
import string
from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import HTTPException

import control.ldap

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from lldap_graphql import Client as LldapGqlClient
    from lldap_graphql import ListGroupsGroups as LldapGqlGroup
    from lldap_graphql import UserFields as LldapGqlUser
    from shared.schemas import AuthenticatedRequest, RegRequest

__all__ = [
    "bootstrap",
    "fetch_group",
    "fetch_user",
    "generate_password",
    "register_user",
    "try_await",
    "verify_token",
]

CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]

logger = logging.getLogger(__name__)


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


async def try_await[T](coro: Awaitable[T]) -> T | None:
    try:
        return await coro

    except Exception as exc:
        err = str(exc)

        if "UNIQUE constraint" in err or "not found" in err:
            logger.info(err)

        else:
            logger.error(err)
            raise

        return None


async def bootstrap(client: LldapGqlClient) -> None:
    await try_await(client.add_telegram_id_attribute())
    await try_await(client.add_telegram_username_attribute())


async def register_user(req: RegRequest, gql: LldapGqlClient) -> str | None:
    user = await try_await(gql.get_user_by_id(req.id_str))
    pw = generate_password(length=20)

    if user is None:
        await gql.create_user(**req.to_lldap_user())

    else:
        await gql.update_user(**req.to_lldap_user())

    def set_password() -> bool:
        return control.ldap.set_password(user_id=req.id_str, password=pw)

    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(None, set_password)
    return pw if ok else None


def verify_token(request: AuthenticatedRequest) -> None:
    if not secrets.compare_digest(request.token, CONTROL_TOKEN):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid token")


async def fetch_user(username: str, gql: LldapGqlClient) -> LldapGqlUser:
    resp = await gql.get_user_by_telegram_username(username)
    if len(resp.users) != 1:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Cannot find user"
        )

    return resp.users[0]


async def fetch_group(display_name: str, gql: LldapGqlClient) -> LldapGqlGroup:
    groups = await gql.list_groups()
    matches = [g for g in groups.groups if g.display_name == display_name]
    if len(matches) != 1:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Cannot find group"
        )

    return matches[0]
