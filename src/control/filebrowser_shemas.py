from pydantic import BaseModel, RootModel

# ruff: noqa: N815  # attribute names are taken from Go source

__all__ = ["Permissions", "Regexp", "Rule", "Sorting", "User", "UsersJson"]


class Permissions(BaseModel):
    admin: bool
    execute: bool
    create: bool
    rename: bool
    modify: bool
    delete: bool
    share: bool
    download: bool


class Sorting(BaseModel):
    by: str = "name"
    asc: bool


class Regexp(BaseModel):
    raw: str


class Rule(BaseModel):
    regex: bool = False
    allow: bool = False
    path: str = ""
    regexp: Regexp | None = None


class User(BaseModel):
    # I dropped the id to patch filebrowser
    id: int | None = None
    username: str
    password: str
    scope: str
    locale: str
    lockPassword: bool
    viewMode: str = "list"
    singleClick: bool
    redirectAfterCopyMove: bool
    perm: Permissions
    commands: list[str] = []
    sorting: Sorting
    rules: list[Rule] = []
    hideDotfiles: bool
    dateFormat: bool
    aceEditorTheme: str = ""


UsersJson = RootModel[list[User]]
