from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from .protocols import current_timestamp

if TYPE_CHECKING:
    from .protocols import TelegramUser

__all__ = [
    "AuthenticatedRequest",
    "HTTPErrorResponse",
    "NotifById",
    "NotifByUser",
    "QueryWithCN",
    "QueryWithDisp",
    "QueryWithId",
    "QueryWithUser",
    "RegRequest",
    "RegResponse",
    "UserMod",
]


class AuthenticatedRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)
    timestamp: int = Field(gt=0, le=9_999_999_999, default_factory=current_timestamp)

    @field_validator("token")
    @classmethod
    def validate_isalnum(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Value is not alphanumeric")

        return v


class QueryWithId(AuthenticatedRequest):
    id: int = Field(gt=0, le=999_999_999_999)

    @property
    def id_str(self) -> str:
        return str(self.id)


class QueryWithUser(AuthenticatedRequest):
    username: str = Field(pattern=r"^\w{5,32}$")


class QueryWithDisp(AuthenticatedRequest):
    display_name: str = Field(min_length=1, max_length=129)


class QueryWithCN(AuthenticatedRequest):
    cn: str = Field(min_length=1, max_length=64)


class RegRequest(QueryWithId, QueryWithUser, QueryWithDisp):
    @classmethod
    def from_telegram_user(cls, user: TelegramUser, token: str) -> RegRequest:
        if user.username is None:
            raise ValueError("@username is required.")

        if user.first_name and user.last_name:
            dn = f"{user.first_name} {user.last_name}"
        elif user.first_name:
            dn = user.first_name
        else:
            dn = user.username

        return cls(id=user.id, username=user.username, display_name=dn, token=token)

    def to_lldap_user(self) -> dict[str, str]:
        return {
            "id": self.id_str,
            "display_name": self.display_name,
            "telegram_id": self.id_str,
            "telegram_username": self.username,
            "email": f"{self.username}@telegram.local",
        }


class RegResponse(BaseModel):
    password: str = Field(min_length=1, max_length=500)


class HTTPErrorResponse(BaseModel):
    detail: str = Field(min_length=1, max_length=500)


class NotifById(QueryWithId):
    message: str = Field(min_length=1, max_length=500)


class NotifByUser(QueryWithUser):
    message: str = Field(min_length=1, max_length=500)


class UserMod(QueryWithUser, QueryWithCN):
    pass
