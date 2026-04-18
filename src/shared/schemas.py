from pydantic import BaseModel, Field, field_validator

__all__ = [
    "HTTPErrorResponse",
    "RegistrationResponse",
    "TelegramNotification",
    "TelegramRegistration",
]


class AuthenticatedRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)

    @field_validator("token")
    @classmethod
    def validate_isalnum(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("Value is not alphanumeric")
        return v


class TelegramRegistration(AuthenticatedRequest):
    id: int = Field(gt=0, le=999_999_999_999)
    username: str = Field(pattern=r"^\w{5,32}$")


class TelegramNotification(AuthenticatedRequest):
    id: int = Field(gt=0, le=999_999_999_999)
    message: str = Field(min_length=1, max_length=500)


class RegistrationResponse(BaseModel):
    password: str = Field(min_length=1, max_length=500)


class HTTPErrorResponse(BaseModel):
    detail: str = Field(min_length=1, max_length=500)
