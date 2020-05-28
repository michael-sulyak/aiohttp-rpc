import json

from aiohttp import http_websocket, web, web_ws

from .base import BaseJsonRpcServer


__all__ = (
    'WsJsonRpcServer',
)


class WsJsonRpcServer(BaseJsonRpcServer):
    async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse:
        if http_request.method == 'GET' and http_request.headers.get('upgrade', '').lower() == 'websocket':
            return await self.handle_websocket_request(http_request)
        else:
            return web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

    async def handle_websocket_request(self, http_request: web.Request) -> web_ws.WebSocketResponse:
        http_request.msg_id = 0
        http_request.pending = {}

        ws = web_ws.WebSocketResponse()
        await ws.prepare(http_request)
        http_request.ws = ws

        while not ws.closed:
            ws_msg = await ws.receive()

            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            await self._handle_ws_msg(http_request, ws_msg)

        return ws

    async def _handle_ws_msg(self, http_request: web.Request, ws_msg: web_ws.WSMessage) -> None:
        input_data = json.loads(ws_msg.data)
        output_data = await self._process_input_data(input_data, http_request=http_request)

        if http_request.ws._writer.transport.is_closing():
            self.clients.remove(http_request)
            await http_request.ws.close()

        await http_request.ws.send_str(self.json_serialize(output_data))
