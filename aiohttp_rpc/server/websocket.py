import asyncio
import json
import typing
import weakref

from aiohttp import http_websocket, web, web_ws

from .base import BaseJsonRpcServer
from .. import errors, protocol, utils


__all__ = (
    'WsJsonRpcServer',
)


class WsJsonRpcServer(BaseJsonRpcServer):
    rcp_websockets: weakref.WeakSet
    _json_response_handler: typing.Optional[typing.Callable] = None

    def __init__(self,
                 *args,
                 json_response_handler: typing.Optional[typing.Callable] = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.rcp_websockets = weakref.WeakSet()
        self._json_response_handler = json_response_handler

    async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse:
        if http_request.method != 'GET' or http_request.headers.get('upgrade', '').lower() != 'websocket':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('GET',))

        return await self._handle_ws_request(http_request)

    async def on_shutdown(self, app: web.Application) -> None:
        # https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown

        for ws in self.rcp_websockets:
            await ws.close(code=http_websocket.WSCloseCode.GOING_AWAY, message='Server shutdown')

        self.rcp_websockets.clear()

    async def _handle_ws_request(self, http_request: web.Request) -> web_ws.WebSocketResponse:
        from aiohttp_rpc import WsJsonRpcClient

        ws_connect = web_ws.WebSocketResponse()
        await ws_connect.prepare(http_request)

        self.rcp_websockets.add(ws_connect)

        ws_rpc_client = WsJsonRpcClient(ws_connect=ws_connect)

        async for ws_msg in ws_connect:
            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            coro = self._handle_ws_message(
                ws_msg=ws_msg,
                ws_connect=ws_connect,
                context={
                    'http_request': http_request,
                    'ws_connect': ws_connect,
                    'ws_rpc_client': ws_rpc_client,
                },
            )
            asyncio.ensure_future(coro)  # TODO: asyncio.create_task(coro) in Python 3.7+

        return ws_connect

    async def _handle_ws_message(self,
                                 ws_msg: web_ws.WSMessage, *,
                                 ws_connect: web_ws.WebSocketResponse,
                                 context: dict) -> None:
        try:
            input_data = json.loads(ws_msg.data)
        except json.JSONDecodeError as e:
            response = protocol.JsonRpcResponse(error=errors.ParseError(utils.get_exc_message(e)))
            json_response = response.to_dict()
        else:
            json_response = await self._process_input_data(input_data, context=context)

        if json_response is None:
            return

        if ws_connect.closed:
            raise errors.ServerError('WS is closed.')

        await ws_connect.send_str(self.json_serialize(json_response))
