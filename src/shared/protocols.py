import time
from typing import Protocol

__all__ = ["LogContext", "TelegramUser", "current_timestamp"]


class TelegramUser(Protocol):
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    restricted: bool | None
    scam: bool | None
    fake: bool | None
    bot: bool | None


def current_timestamp() -> int:
    return int(time.time())


class LogContext(dict[str, int | bool | str]):
    def __init__(
        self, api: str, timestamp: int | None = None, **kwargs: int | bool | str
    ) -> None:
        ts = timestamp if timestamp is not None else current_timestamp()
        super().__init__(api=api, timestamp=ts, **kwargs)

    def copy(self) -> LogContext:
        res = LogContext.__new__(LogContext)
        dict.__init__(res, self)
        return res
