import json
import logging
import typing

import aiohttp
from aiohttp import web

from .base import BaseJSONRPCServer
from .. import errors, middlewares, protocol


__all__ = (
    'JSONRPCServer',
    'rpc_server',
)

logger = logging.getLogger(__name__)


class JSONRPCServer(BaseJSONRPCServer):
    async def handle_http_request(self, http_request: web.Request) -> web.Response:
        if http_request.method != 'POST':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

        try:
            input_data = await http_request.json(loads=self._json_deserialize)
        except (aiohttp.ContentTypeError, json.JSONDecodeError,):
            logger.warning('Invalid JSON data', exc_info=True)
            response = protocol.JSONRPCResponse(error=errors.ParseError(data={'details': 'Invalid JSON'}))
            return web.json_response(response.dump(), dumps=self._json_serialize)

        output_data = await self._process_input_data(input_data, context={'http_request': http_request})

        if output_data is None:
            return web.Response(status=204)  # Note: No content for notifications.

        if isinstance(output_data, typing.Sequence):
            raw_output_data = tuple(response.dump() for response in output_data)
        else:
            raw_output_data = output_data.dump()  # type: ignore

        return web.json_response(raw_output_data, dumps=self._json_serialize)


rpc_server = JSONRPCServer(
    middlewares=middlewares.DEFAULT_MIDDLEWARES,
)
