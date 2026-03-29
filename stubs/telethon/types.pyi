class User:
    id: int
    username: str | None
    restricted: bool
    scam: bool
    fake: bool
    bot: bool

    def to_dict(self) -> dict[str, object]: ...
