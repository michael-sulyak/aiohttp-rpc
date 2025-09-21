import asyncio
import json
import typing

import aiohttp

from .base import BaseJSONRPCClient
from .. import errors, typedefs, utils


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
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 json_deserialize: typedefs.JSONDecoderType = utils.json_deserialize,
                 **request_kwargs) -> None:
        super().__init__(
            json_serialize=json_serialize,
            json_deserialize=json_deserialize,
        )
        self.url = url
        self.session = session
        self.request_kwargs = request_kwargs
        self._session_is_outer = session is not None  # We don't close an outer session.

    async def connect(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession(json_serialize=self._json_serialize, **self.request_kwargs)

    async def disconnect(self) -> None:
        if self.session is not None and not self._session_is_outer:
            await self.session.close()

    async def send_json(self,
                        data: typing.Any, *,
                        ignore_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        assert self.session is not None

        try:
            http_response = await self.session.post(self.url, json=data, **kwargs)
        except (aiohttp.ClientError, asyncio.TimeoutError,) as e:
            raise errors.TransportError from e

        if ignore_response:
            await http_response.read()
            return None, {'http_response': http_response}

        body_bytes = await http_response.read()

        if body_bytes:
            body_text = body_bytes.strip().decode(
                http_response.get_encoding(),
                errors='replace',
            )
        else:
            body_text = None

        if not body_text:
            if 200 <= http_response.status < 300:
                # Expected a JSON-RPC response, got nothing:
                raise errors.EmptyResponse()

            # Non-2xx with empty body: transport-level error
            raise errors.HTTPStatusError(
                data={
                    'status': http_response.status,
                    'message': http_response.reason,
                },
            )

        # Try to parse JSON regardless of Content-Type:
        try:
            json_response = self._json_deserialize(body_text)
        except (json.JSONDecodeError, TypeError, ValueError,) as e:
            if 200 <= http_response.status < 300:
                # Body present but invalid JSON: true JSON-RPC parse error
                raise errors.ParseError(data={'details': 'Invalid JSON'}) from e

            # Non-2xx with non-JSON body: treat as HTTP/transport error
            raise errors.HTTPStatusError(
                data={
                    'status': http_response.status,
                    'message': http_response.reason,
                    'body': body_text[:512]},
            ) from e

        # If we got JSON, hand it to the protocol layer even on non-2xx:
        return json_response, {'http_response': http_response}
