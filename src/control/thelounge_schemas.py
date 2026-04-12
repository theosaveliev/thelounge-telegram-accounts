from typing import Any

from pydantic import BaseModel

# ruff: noqa: N815  # attribute names are taken from TypeScript source

__all__ = [
    "BrowserInfo",
    "ChanConfig",
    "ClientPushSubscription",
    "NetworkConfig",
    "SessionInfo",
    "UserConfig",
]


class BrowserInfo(BaseModel):
    language: str | None = None
    ip: str | None = None
    hostname: str | None = None
    isSecure: bool | None = None


class ChanConfig(BaseModel):
    name: str
    key: str | None = None
    muted: bool | None = None
    type: str | None = None


class NetworkConfig(BaseModel):
    nick: str
    name: str
    host: str
    port: int
    tls: bool
    userDisconnected: bool
    rejectUnauthorized: bool
    password: str
    awayMessage: str
    commands: list[Any]
    username: str
    realname: str
    leaveMessage: str
    sasl: str
    saslAccount: str
    saslPassword: str
    channels: list[ChanConfig]
    # I dropped the uuid to patch thelounge
    uuid: str | None = None
    proxyHost: str
    proxyPort: int
    proxyUsername: str
    proxyPassword: str
    proxyEnabled: bool
    highlightRegex: str | None = None
    ignoreList: list[Any]


class ClientPushSubscription(BaseModel):
    endpoint: str
    keys: dict[str, str]


class SessionInfo(BaseModel):
    lastUse: int
    ip: str
    agent: str
    pushSubscription: ClientPushSubscription | None = None


class UserConfig(BaseModel):
    log: bool
    password: str
    sessions: dict[str, SessionInfo]
    clientSettings: dict[str, Any]
    networks: list[NetworkConfig] | None = None
    browser: BrowserInfo | None = None
