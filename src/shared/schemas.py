from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from telethon.types import User as TelegramUser

    from lldap_graphql import UserFields as LLDAPUser

__all__ = [
    "GroupRequest",
    "HTTPErrorResponse",
    "NotificationById",
    "NotificationByUsername",
    "RegistrationResponse",
    "User",
    "UserFilter",
]

IRCD_MAX_NICK_LENGTH = 31
TELEGRAM_USERNAME_PATTERN = r"^[a-zA-Z0-9_]+$"

# LLDAP uses sqlite3 varchar(255)
Identifier = Annotated[str, Field(min_length=1, max_length=255)]

Username = Annotated[
    str,
    Field(
        min_length=1, max_length=IRCD_MAX_NICK_LENGTH, pattern=TELEGRAM_USERNAME_PATTERN
    ),
]

# Telegram User ID range
Number = Annotated[int, Field(ge=1, le=999_999_999_999)]


class User(BaseModel):
    id: Number
    username: Username
    full_name: Identifier

    @classmethod
    def from_telegram_user(cls, user: TelegramUser) -> User:
        if not user.username:
            raise ValueError("Telegram @username is required.")

        if len(user.username) > IRCD_MAX_NICK_LENGTH:
            raise ValueError("Telegram @username is too long.")

        if user.restricted or user.scam or user.fake:
            raise ValueError("Telegram account has active restrictions.")

        if user.bot:
            raise ValueError("No bots allowed.")

        if user.first_name and user.last_name:
            dn = f"{user.first_name} {user.last_name}"
        elif user.first_name:
            dn = user.first_name
        else:
            dn = user.username

        return cls(id=user.id, username=user.username, full_name=dn)

    @classmethod
    def from_lldap_user(cls, user: LLDAPUser) -> User:
        try:
            attr = next(a for a in user.attributes if a.name == "telegramid")
            tg_id = int(attr.value[0])

        except IndexError, ValueError, StopIteration:
            raise ValueError(f"Missing Telegram Id: {user.id}") from None

        return cls(id=tg_id, username=user.id, full_name=user.display_name)

    def to_lldap_user_dict(self) -> dict[str, str]:
        return {
            "id": self.username,
            "telegram_id": str(self.id),
            "display_name": self.full_name,
            "email": f"{self.username}@control",
        }


class UserFilter(BaseModel):
    telegram_id: Number | None = None
    full_name: Identifier | None = None
    group: Identifier | None = None


class RegistrationResponse(BaseModel):
    password: Identifier


class HTTPErrorResponse(BaseModel):
    detail: Identifier


class NotificationById(BaseModel):
    recipient: Number
    message: Identifier


class NotificationByUsername(BaseModel):
    recipient: Username
    message: Identifier


class GroupRequest(BaseModel):
    group: Identifier
