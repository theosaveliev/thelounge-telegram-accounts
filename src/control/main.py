import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, cast

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from httpx import AsyncClient as HttpAsyncClient

from control.functions import (
    bootstrap,
    fetch_group,
    fetch_user,
    register_user,
    verify_token,
)
from lldap_graphql import Client as LldapGqlClient
from lldap_jwt.client import LldapJwtClient
from shared.schemas import (
    NotifById,
    NotifByUser,
    QueryWithCN,
    QueryWithDisp,
    QueryWithId,
    QueryWithUser,
    RegRequest,
    RegResponse,
    UserMod,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

__all__ = ["app", "run"]

CONTROL_LISTEN = os.environ["CONTROL_LISTEN"]
CONTROL_PORT = int(os.environ["CONTROL_PORT"])
BOT_URL = os.environ["BOT_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
LLDAP_HTTP_URL = os.environ["LLDAP_HTTP_URL"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    jwt = LldapJwtClient()
    gql_url = f"{LLDAP_HTTP_URL}/api/graphql"
    gql = app.state.gql_client = LldapGqlClient(url=gql_url, http_client=jwt)
    hcl = app.state.http_client = HttpAsyncClient()
    await bootstrap(gql)

    yield

    await jwt.aclose()
    await hcl.aclose()


def get_gql_client(request: Request) -> LldapGqlClient:
    return cast("LldapGqlClient", request.app.state.gql_client)  # pyright: ignore[reportAny]


def get_http_client(request: Request) -> HttpAsyncClient:
    return cast("HttpAsyncClient", request.app.state.http_client)  # pyright: ignore[reportAny]


GqlClient = Annotated[LldapGqlClient, Depends(get_gql_client)]
HttpClient = Annotated[HttpAsyncClient, Depends(get_http_client)]

app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
auth_app = APIRouter(dependencies=[Depends(verify_token)])


@app.get("/health")
async def health() -> Response:
    return Response(status_code=HTTPStatus.OK)


@auth_app.post("/register_user")
async def register(req: RegRequest, gql: GqlClient) -> JSONResponse:
    pw = await register_user(req, gql)

    if pw is None:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Cannot register user"
        )

    res = RegResponse(password=pw).model_dump()
    return JSONResponse(status_code=HTTPStatus.CREATED, content=res)


@auth_app.post("/notify_user")
async def notify_user(req: NotifByUser, gql: GqlClient, hcl: HttpClient) -> Response:
    user = await fetch_user(req.username, gql)
    notif = NotifById(token=BOT_TOKEN, id=int(user.id), message=req.message)
    resp = await hcl.post(f"{BOT_URL}/notify", json=notif.model_dump())
    return Response(status_code=resp.status_code)


@auth_app.post("/list_users")
async def list_users(gql: GqlClient) -> JSONResponse:
    resp = await gql.list_users()
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/get_user_by_id")
async def get_user_id(req: QueryWithId, gql: GqlClient) -> JSONResponse:
    resp = await gql.get_user_by_id(req.id_str)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/get_user_by_username")
async def get_user_username(req: QueryWithUser, gql: GqlClient) -> JSONResponse:
    user = await fetch_user(req.username, gql)
    return JSONResponse(status_code=HTTPStatus.OK, content=user.model_dump())


@auth_app.post("/get_users_by_display_name")
async def get_users_disp(req: QueryWithDisp, gql: GqlClient) -> JSONResponse:
    resp = await gql.get_users_by_display_name(req.display_name)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/get_users_by_group")
async def get_users_group(req: QueryWithCN, gql: GqlClient) -> JSONResponse:
    resp = await gql.get_users_by_group(req.cn)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/delete_user_by_username")
async def delete_user_name(req: QueryWithUser, gql: GqlClient) -> JSONResponse:
    user = await fetch_user(req.username, gql)
    ret = await gql.delete_user(user.id)
    return JSONResponse(status_code=HTTPStatus.OK, content=ret.model_dump())


@auth_app.post("/list_groups")
async def list_groups(gql: GqlClient) -> JSONResponse:
    resp = await gql.list_groups()
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/create_group")
async def create_group(req: QueryWithCN, gql: GqlClient) -> JSONResponse:
    resp = await gql.create_group(req.cn)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/delete_group")
async def delete_group(req: QueryWithCN, gql: GqlClient) -> JSONResponse:
    group = await fetch_group(req.cn, gql)
    resp = await gql.delete_group(group.id)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/add_user_to_group")
async def add_user_to_group(req: UserMod, gql: GqlClient) -> JSONResponse:
    user = await fetch_user(req.username, gql)
    group = await fetch_group(req.cn, gql)
    resp = await gql.add_user_to_group(user.id, group.id)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


@auth_app.post("/remove_user_from_group")
async def remove_user_from_group(req: UserMod, gql: GqlClient) -> JSONResponse:
    user = await fetch_user(req.username, gql)
    group = await fetch_group(req.cn, gql)
    resp = await gql.remove_user_from_group(user.id, group.id)
    return JSONResponse(status_code=HTTPStatus.OK, content=resp.model_dump())


app.include_router(auth_app)


def run() -> None:
    uvicorn.run(
        "control.main:app",
        host=CONTROL_LISTEN,
        port=CONTROL_PORT,
        loop="uvloop",
        log_config=None,
    )
