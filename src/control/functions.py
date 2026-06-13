import asyncio
import secrets
import string
from typing import TYPE_CHECKING

import control.ldap

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from lldap_graphql import Client as GQLClient
    from shared.schemas import User

__all__ = [
    "generate_password",
    "get_group_id",
    "register_user",
    "try_ignore_unique_constraint",
]


# GQL doesn't provide exception class, so search for a string
async def try_ignore_unique_constraint[T](coro: Awaitable[T]) -> None:
    try:
        await coro

    except Exception as exc:
        if "UNIQUE constraint failed" not in str(exc):
            raise


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


async def register_user(user: User, gql: GQLClient) -> str:
    """Create or update LLDAP user."""
    lldap_user = user.to_lldap_user_dict()
    pw = generate_password(length=20)

    found = await gql.get_users_by_telegram_id(str(user.id))
    updating = False
    for old in found.users:
        if old.id == user.username:
            updating = True

        else:
            await gql.delete_user(old.id)

    if updating:
        await gql.update_user(**lldap_user)

    else:
        await gql.create_user(**lldap_user)

    def set_password() -> None:
        control.ldap.set_password(user_id=user.username, password=pw)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, set_password)
    return pw


async def get_group_id(group_name: str, gql: GQLClient) -> int:
    groups = await gql.list_groups()
    try:
        group = next(g for g in groups.groups if g.display_name == group_name)

    except StopIteration:
        raise ValueError(f"Group not found: {group_name}") from None

    return group.id
