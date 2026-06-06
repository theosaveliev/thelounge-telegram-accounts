class User:
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    restricted: bool | None
    scam: bool | None
    fake: bool | None
    bot: bool | None

    def to_dict(self) -> dict[str, object]: ...
