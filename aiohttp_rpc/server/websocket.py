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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.rcp_websockets = weakref.WeakSet()

    async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse:
        if http_request.method != 'GET' or http_request.headers.get('upgrade', '').lower() != 'websocket':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('GET',))

        return await self.handle_websocket_request(http_request)

    async def handle_websocket_request(self, http_request: web.Request) -> web_ws.WebSocketResponse:
        ws_connect = web_ws.WebSocketResponse()
        await ws_connect.prepare(http_request)

        self.rcp_websockets.add(ws_connect)

        async for ws_msg in ws_connect:
            if ws_msg.type == http_websocket.WSMsgType.TEXT:
                coro = self.handle_ws_message(
                    ws_msg=ws_msg,
                    ws_connect=ws_connect,
                    http_request=http_request,
                )
                asyncio.ensure_future(coro)  # TODO: asyncio.create_task(coro) in Python 3.7+
            elif ws_msg.type == http_websocket.WSMsgType.ERROR:
                break

        return ws_connect

    async def on_shutdown(self, app: web.Application) -> None:
        # https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown

        for ws in self.rcp_websockets:
            await ws.close(code=http_websocket.WSCloseCode.GOING_AWAY, message='Server shutdown')

        self.rcp_websockets.clear()

    async def handle_ws_message(self,
                                ws_msg: web_ws.WSMessage, *,
                                ws_connect: web_ws.WebSocketResponse,
                                http_request: typing.Optional[web.Request] = None) -> None:
        try:
            input_data = json.loads(ws_msg.data)
        except json.JSONDecodeError as e:
            response = protocol.JsonRpcResponse(error=errors.ParseError(utils.get_exc_message(e)))
            json_response = response.to_dict()
        else:
            json_response = await self._process_input_data(input_data, context={
                'http_request': http_request,
                'ws_connect': ws_connect,
            })

        if json_response is None:
            return

        if ws_connect.closed:
            raise errors.ServerError('WS is closed.')

        await ws_connect.send_str(self.json_serialize(json_response))
