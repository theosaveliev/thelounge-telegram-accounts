from pydantic import BaseModel, Field

__all__ = ["SFTPGoAdmin", "SFTPGoBackup", "SFTPGoUser"]


class SFTPGoUser(BaseModel):
    status: int = 1
    username: str
    password: str
    has_password: bool = True
    home_dir: str
    permissions: dict[str, list[str]] = Field(default_factory=lambda: {"/": ["*"]})


class SFTPGoAdmin(BaseModel):
    status: int = 1
    username: str
    password: str
    permissions: list[str] = Field(default_factory=lambda: ["*"])


class SFTPGoBackup(BaseModel):
    version: int = 17
    users: list[SFTPGoUser] = Field(default_factory=list)
    admins: list[SFTPGoAdmin] = Field(default_factory=list)
