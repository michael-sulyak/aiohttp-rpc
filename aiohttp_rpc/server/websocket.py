import asyncio
import json
import weakref

from aiohttp import http_websocket, web, web_ws

from .base import BaseJsonRpcServer


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
        ws = web_ws.WebSocketResponse()
        await ws.prepare(http_request)

        self.rcp_websockets.add(ws)

        async for ws_msg in ws:
            if ws_msg.type == http_websocket.WSMsgType.TEXT:
                coro = self._handle_ws_msg(
                    ws=ws,
                    http_request=http_request,
                    ws_msg=ws_msg,
                )
                asyncio.ensure_future(coro)  # asyncio.create_task(coro) in Python 3.7+
            elif ws_msg.type == http_websocket.WSMsgType.ERROR:
                break

        return ws

    async def on_shutdown(self, app: web.Application) -> None:
        # https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown

        for ws in self.rcp_websockets:
            await ws.close(code=http_websocket.WSCloseCode.GOING_AWAY, message='Server shutdown')

        self.rcp_websockets.clear()

    async def _handle_ws_msg(self, *,
                             ws: web_ws.WebSocketResponse,
                             http_request: web.Request,
                             ws_msg: web_ws.WSMessage) -> None:
        input_data = json.loads(ws_msg.data)
        output_data = await self._process_input_data(input_data, http_request=http_request)

        if not ws.closed:
            await ws.send_str(self.json_serialize(output_data))
