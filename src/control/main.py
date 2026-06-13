import logging
import os
import secrets
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, cast

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from httpx import AsyncClient as HTTPAsyncClient

from control.functions import get_group_id, register_user, try_ignore_unique_constraint
from lldap_graphql import BaseModel as GQLBaseModel
from lldap_graphql import Client as GQLClient
from lldap_jwt.client import JWTClient
from shared.schemas import (
    GroupRequest,
    NotificationById,
    NotificationByUsername,
    RegistrationResponse,
    User,
    UserFilter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


__all__ = ["app", "run"]

CONTROL_LISTEN = os.environ["CONTROL_LISTEN"]
CONTROL_PORT = int(os.environ["CONTROL_PORT"])
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
BOT_URL = os.environ["BOT_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
LLDAP_HTTP_URL = os.environ["LLDAP_HTTP_URL"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    jwt_client = JWTClient()
    url = f"{LLDAP_HTTP_URL}/api/graphql"
    app.state.gql_client = gql = GQLClient(url=url, http_client=jwt_client)
    app.state.http_client = http_client = HTTPAsyncClient()
    await try_ignore_unique_constraint(gql.add_telegram_id_attribute())

    yield

    await jwt_client.aclose()
    await http_client.aclose()


def get_gql_client(request: Request) -> GQLClient:
    return cast("GQLClient", request.app.state.gql_client)  # pyright: ignore[reportAny]


def get_http_client(request: Request) -> HTTPAsyncClient:
    return cast("HTTPAsyncClient", request.app.state.http_client)  # pyright: ignore[reportAny]


GQL = Annotated[GQLClient, Depends(get_gql_client)]
HTTP = Annotated[HTTPAsyncClient, Depends(get_http_client)]

header_scheme = APIKeyHeader(name="X-API-Key")


async def verify_token(api_key: Annotated[str, Depends(header_scheme)]) -> None:
    if not secrets.compare_digest(api_key, CONTROL_TOKEN):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Invalid token")


app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
auth_app = APIRouter(dependencies=[Depends(verify_token)])


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


# shared.shemas.User is the API perspective, not LLDAP
# LLDAP does not support filtering by attributes, and therefore:
# User.id == LLDAP telegramid
# User.username == LLDAP id
# https://github.com/lldap/lldap/issues/858


@auth_app.get("/user")
async def get_users(
    filters: Annotated[UserFilter, Depends()], gql: GQL
) -> JSONResponse:

    if sum(1 for _, v in filters if v is not None) > 1:  # pyright: ignore[reportAny]
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Too many params")

    resp: GQLBaseModel

    if filters.telegram_id is not None:
        resp = await gql.get_users_by_telegram_id(str(filters.telegram_id))

    elif filters.full_name is not None:
        resp = await gql.get_users_by_display_name(filters.full_name)

    elif filters.group is not None:
        resp = await gql.get_users_by_group(filters.group)

    else:
        resp = await gql.list_users()

    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.put("/user")
async def put_user(req: User, gql: GQL) -> JSONResponse:
    pw = await register_user(req, gql)
    resp = RegistrationResponse(password=pw).model_dump()
    return JSONResponse(status_code=HTTPStatus.OK, content=resp)


@auth_app.get("/user/{username}")
async def get_user(username: str, gql: GQL) -> JSONResponse:
    resp = await gql.get_user_by_id(username)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.delete("/user/{username}")
async def delete_user(username: str, gql: GQL) -> Response:
    await gql.delete_user(username)
    return Response(status_code=HTTPStatus.OK)


@auth_app.get("/group")
async def list_groups(gql: GQL) -> JSONResponse:
    resp = await gql.list_groups()
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/group")
async def create_group(req: GroupRequest, gql: GQL) -> JSONResponse:
    resp = await gql.create_group(req.group)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.delete("/group/{group_name}")
async def delete_group(group_name: str, gql: GQL) -> Response:
    group_id = await get_group_id(group_name, gql)
    await gql.delete_group(group_id)
    return Response(status_code=HTTPStatus.OK)


@auth_app.put("/group/{group_name}/member/{username}")
async def add_user_to_group(group_name: str, username: str, gql: GQL) -> Response:
    group_id = await get_group_id(group_name, gql)
    await try_ignore_unique_constraint(gql.add_user_to_group(username, group_id))
    return Response(status_code=HTTPStatus.OK)


@auth_app.delete("/group/{group_name}/member/{username}")
async def remove_user_from_group(group_name: str, username: str, gql: GQL) -> Response:
    group_id = await get_group_id(group_name, gql)
    await gql.remove_user_from_group(username, group_id)
    return Response(status_code=HTTPStatus.OK)


@auth_app.post("/notification")
async def notify_user(req: NotificationByUsername, gql: GQL, hcl: HTTP) -> Response:
    lldap_user = await gql.get_user_by_id(req.recipient)
    user = User.from_lldap_user(lldap_user.user)
    msg = NotificationById(recipient=user.id, message=req.message)
    url = f"{BOT_URL}/notification"
    headers = {"X-API-Key": BOT_TOKEN}
    resp = await hcl.post(url, headers=headers, json=msg.model_dump())
    return Response(status_code=resp.status_code)


app.include_router(auth_app)


def run() -> None:
    uvicorn.run(
        "control.main:app",
        host=CONTROL_LISTEN,
        port=CONTROL_PORT,
        loop="uvloop",
        log_config=None,
    )
