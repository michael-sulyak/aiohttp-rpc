import typing

import aiohttp

from .base import BaseJsonRpcClient
from .. import errors, utils


__all__ = (
    'JsonRpcClient',
)


class JsonRpcClient(BaseJsonRpcClient):
    url: str
    session: typing.Optional[aiohttp.ClientSession]
    request_kwargs: dict
    _is_outer_session: bool

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 **request_kwargs) -> None:
        self.url = url
        self.session = session
        self.request_kwargs = request_kwargs
        self._is_outer_session = session is not None

    async def connect(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(json_serialize=self.json_serialize)

    async def disconnect(self) -> None:
        if not self._is_outer_session:
            await self.session.close()

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        http_response = await self.session.post(self.url, json=data, **self.request_kwargs)

        try:
            json_response = await http_response.json()
        except aiohttp.ContentTypeError as e:
            raise errors.ParseError(utils.get_exc_message(e)) from e

        if without_response:
            return None, None

        return json_response, {'http_response': http_response}
