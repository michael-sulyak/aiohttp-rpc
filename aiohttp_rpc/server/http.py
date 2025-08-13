import json

import aiohttp
from aiohttp import web

from .base import BaseJSONRPCServer
from .. import errors, middlewares, protocol, utils


__all__ = (
    'JSONRPCServer',
    'rpc_server',
)


class JSONRPCServer(BaseJSONRPCServer):
    async def handle_http_request(self, http_request: web.Request) -> web.Response:
        if http_request.method != 'POST':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

        if self._max_payload_bytes is not None:
            # Prefer Content-Length when present (fast path):
            if http_request.content_length is not None and http_request.content_length > self._max_payload_bytes:
                raise web.HTTPRequestEntityTooLarge(
                    max_size=self._max_payload_bytes,
                    actual_size=http_request.content_length,
                )

            # Otherwise, read and check as a safe fallback:
            raw = await http_request.read()
            if len(raw) > self._max_payload_bytes:
                raise web.HTTPRequestEntityTooLarge(
                    max_size=self._max_payload_bytes,
                    actual_size=len(raw),
                )

        try:
            input_data = await http_request.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError,) as e:
            response = protocol.JSONRPCResponse(error=errors.ParseError(utils.get_exc_message(e)))
            return web.json_response(response.dump(), dumps=self.json_serialize)

        output_data = await self._process_input_data(input_data, context={'http_request': http_request})

        if output_data is None:
            return web.Response(status=204)  # Note: No content for notifications.

        return web.json_response(output_data, dumps=self.json_serialize)


rpc_server = JSONRPCServer(
    middlewares=middlewares.DEFAULT_MIDDLEWARES,
)
