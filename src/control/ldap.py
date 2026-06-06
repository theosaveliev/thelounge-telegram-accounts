import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import ldap3
from ldap3 import Connection, Server

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["set_password"]

LLDAP_LDAP_URL = os.environ["LLDAP_LDAP_URL"]
LLDAP_BASE_DN = os.environ["LLDAP_BASE_DN"]
LLDAP_USERNAME = os.environ["LLDAP_USERNAME"]
LLDAP_PASSWORD = os.environ["LLDAP_PASSWORD"]

logger = logging.getLogger(__name__)


@contextmanager
def make_connection() -> Generator[Connection]:
    server = Server(host=LLDAP_LDAP_URL, get_info=ldap3.ALL, mode=ldap3.IP_V4_PREFERRED)
    app_dn = f"uid={LLDAP_USERNAME},{LLDAP_BASE_DN}"
    conn = Connection(
        server=server,
        user=app_dn,
        password=LLDAP_PASSWORD,
        auto_bind=ldap3.AUTO_BIND_NO_TLS,
        client_strategy=ldap3.SYNC,
    )

    try:
        yield conn

    finally:
        conn.unbind()  # type: ignore[no-untyped-call]


def set_password(user_id: str, password: str) -> bool:
    user_dn = f"uid={user_id},{LLDAP_BASE_DN}"
    with make_connection() as conn:
        conn.extend.standard.modify_password(  # pyright: ignore[reportAny]
            user_dn, old_password=None, new_password=password
        )

        if conn.result is None:  # pyright: ignore[reportAny]
            return False

        return bool(conn.result["result"] == 0)  # pyright: ignore[reportAny]
