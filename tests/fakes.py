from __future__ import annotations

from catocode.auth.base import Auth


class StaticAuth(Auth):
    def __init__(self, token: str = "ghu_test") -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token

    def auth_type(self) -> str:
        return "static"
