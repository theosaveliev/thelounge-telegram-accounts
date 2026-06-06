# ruff: noqa: ANN401
# pyright: reportAny=false

import os
from typing import Any

from httpx import AsyncClient, HTTPError, Request, Response

from shared.protocols import current_timestamp

__all__ = ["LldapJwtClient"]

LLDAP_HTTP_URL = os.environ["LLDAP_HTTP_URL"]
LLDAP_USERNAME = os.environ["LLDAP_USERNAME"]
LLDAP_PASSWORD = os.environ["LLDAP_PASSWORD"]


class LldapJwtClient(AsyncClient):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.token: str | None = None
        self.refresh_token: str | None = None
        self.expires: int = 0

    def update_tokens(self, token: str, refresh_token: str) -> None:
        self.token = token
        self.refresh_token = refresh_token

        # https://github.com/lldap/lldap/blob/main/docs/scripting.md#using-the-token
        self.expires = current_timestamp() + 24 * 60 * 60 - 300

    async def login(self) -> None:
        url = f"{LLDAP_HTTP_URL}/auth/simple/login"
        creds = {"username": LLDAP_USERNAME, "password": LLDAP_PASSWORD}
        res = await self.send_request(method="POST", url=url, json=creds)
        res.raise_for_status()
        data = res.json()
        self.update_tokens(data["token"], data["refreshToken"])

    async def refresh(self) -> None:
        try:
            url = f"{LLDAP_HTTP_URL}/auth/refresh"
            headers = {"Authorization": f"Bearer {self.refresh_token}"}
            res = await self.send_request(method="GET", url=url, headers=headers)
            res.raise_for_status()
            data = res.json()
            self.update_tokens(data["token"], data["refreshToken"])

        except HTTPError:
            await self.login()

    async def ensure_token(self) -> None:
        if self.token is None:
            await self.login()

        elif current_timestamp() > self.expires:
            await self.refresh()

    async def send_request(self, method: str, url: str, **kwargs: Any) -> Response:
        request = self.build_request(method, url, **kwargs)
        return await super().send(request)

    async def send(self, request: Request, **kwargs: Any) -> Response:
        await self.ensure_token()
        request.headers["Authorization"] = f"Bearer {self.token}"
        return await super().send(request, **kwargs)
