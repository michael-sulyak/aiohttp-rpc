import json
import typing

import aiohttp

from .base import BaseJSONRPCClient
from .. import errors, utils


__all__ = (
    'JSONRPCClient',
)


class JSONRPCClient(BaseJSONRPCClient):
    url: str
    session: typing.Optional[aiohttp.ClientSession]
    request_kwargs: dict
    _session_is_outer: bool

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 **request_kwargs) -> None:
        super().__init__()
        self.url = url
        self.session = session
        self.request_kwargs = request_kwargs
        self._session_is_outer = session is not None  # We don't close an outer session.

    async def connect(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(json_serialize=self.json_serialize, **self.request_kwargs)

    async def disconnect(self) -> None:
        if self.session is not None and not self._session_is_outer:
            await self.session.close()

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        assert self.session is not None

        http_response = await self.session.post(self.url, json=data, **kwargs)

        if without_response:
            # Note: Drain so the connection can be reused.
            await http_response.read()
            return None, None

        raw_data = await http_response.read()

        if raw_data:
            try:
                json_response = await http_response.json(loads=self.json_deserialize)
            except (aiohttp.ContentTypeError, json.JSONDecodeError,) as e:
                raise errors.ParseError(utils.get_exc_message(e)) from e
        else:
            json_response = None

        return json_response, {'http_response': http_response}
