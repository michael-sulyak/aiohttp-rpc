import json

from aiohttp import web

from .base import BaseJsonRpcServer
from .. import errors, middlewares, protocol, utils


__all__ = (
    'JsonRpcServer',
    'rpc_server',
)


class JsonRpcServer(BaseJsonRpcServer):
    async def handle_http_request(self, http_request: web.Request) -> web.Response:
        if http_request.method != 'POST':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

        try:
            input_data = await http_request.json()
        except json.JSONDecodeError as e:
            response = protocol.JsonRpcResponse(error=errors.ParseError(utils.get_exc_message(e)))
            return web.json_response(response.to_dict(), dumps=self.json_serialize)

        output_data = await self._process_input_data(input_data, http_request=http_request)

        return web.json_response(output_data, dumps=self.json_serialize)


rpc_server = JsonRpcServer(
    middlewares=middlewares.DEFAULT_MIDDLEWARES,
)
