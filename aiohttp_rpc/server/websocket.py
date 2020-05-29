import json
import weakref

from aiohttp import http_websocket, web, web_ws

from .base import BaseJsonRpcServer


__all__ = (
    'WsJsonRpcServer',
)


class WsJsonRpcServer(BaseJsonRpcServer):
    ws_state_key = 'rcp_websockets'

    async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse:
        if http_request.method != 'GET' or http_request.headers.get('upgrade', '').lower() != 'websocket':
            return web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

        if self.ws_state_key not in http_request.app:
            http_request.app[self.ws_state_key] = weakref.WeakSet()

        return await self.handle_websocket_request(http_request)

    async def handle_websocket_request(self, http_request: web.Request) -> web_ws.WebSocketResponse:
        http_request.msg_id = 0
        http_request.pending = {}

        ws = web_ws.WebSocketResponse()
        await ws.prepare(http_request)
        http_request['ws'] = ws
        http_request.app[self.ws_state_key].add(ws)

        while not ws.closed:
            ws_msg = await ws.receive()

            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            await self._handle_ws_msg(http_request, ws_msg)

        http_request.app[self.ws_state_key].discard(ws)
        return ws

    async def on_shutdown(self, app: web.Application) -> None:
        # https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown

        if self.ws_state_key not in app:
            return

        for ws in set(app[self.ws_state_key]):
            await ws.close(code=http_websocket.WSCloseCode.GOING_AWAY, message='Server shutdown')

        app[self.ws_state_key].clear()

    async def _handle_ws_msg(self, http_request: web.Request, ws_msg: web_ws.WSMessage) -> None:
        input_data = json.loads(ws_msg.data)
        output_data = await self._process_input_data(input_data, http_request=http_request)
        ws = http_request['ws']

        if ws._writer.transport.is_closing():
            await ws.close()
            http_request.app[self.ws_state_key].discard(ws)

        await http_request['ws'].send_str(self.json_serialize(output_data))
