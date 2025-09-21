import asyncio
import json
import logging
import typing
import weakref

from aiohttp import http_websocket, web, web_ws

from .base import BaseJSONRPCServer
from .. import errors, protocol, typedefs


__all__ = (
    'WSJSONRPCServer',
)

logger = logging.getLogger(__name__)


class WSJSONRPCServer(BaseJSONRPCServer):
    rpc_websockets: weakref.WeakSet
    allowed_origins: typing.Optional[typing.Container[str]]
    ws_response_cls: typing.Type[web_ws.WebSocketResponse]
    ws_response_kwargs: typing.Dict
    _json_response_handler: typing.Optional[typedefs.WSJSONResponseHandler] = None
    _background_tasks: typing.Set

    def __init__(self,
                 *args,
                 allowed_origins: typing.Optional[typing.Container[str]] = None,
                 json_response_handler: typing.Optional[typing.Callable] = None,
                 ws_response_cls: typing.Type[web_ws.WebSocketResponse] = web_ws.WebSocketResponse,
                 ws_response_kwargs: typing.Optional[typing.Dict] = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.allowed_origins = allowed_origins
        self.rpc_websockets = weakref.WeakSet()
        self.ws_response_cls = ws_response_cls
        self.ws_response_kwargs = ws_response_kwargs or {'max_msg_size': 1_048_576}
        self._json_response_handler = json_response_handler
        self._background_tasks = set()

    async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse:
        if http_request.method != 'GET' or http_request.headers.get('upgrade', '').lower() != 'websocket':
            raise web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('GET',))

        if self.allowed_origins is not None:
            origin = http_request.headers.get('Origin')

            if origin not in self.allowed_origins:
                raise web.HTTPForbidden(reason='Origin not allowed.')

        return await self._handle_ws_request(http_request)

    async def on_shutdown(self, app: web.Application) -> None:
        # https://docs.aiohttp.org/en/stable/web_advanced.html#graceful-shutdown

        for ws in self.rpc_websockets:
            await ws.close(code=http_websocket.WSCloseCode.GOING_AWAY, message='Server shutdown')

        self.rpc_websockets.clear()

        for task in tuple(self._background_tasks):
            task.cancel()

        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

    async def _handle_ws_request(self, http_request: web.Request) -> web_ws.WebSocketResponse:
        ws_connect = self.ws_response_cls(**self.ws_response_kwargs)
        await ws_connect.prepare(http_request)

        self.rpc_websockets.add(ws_connect)

        ws_msg: http_websocket.WSMessage

        async for ws_msg in ws_connect:
            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            coro = self._handle_ws_message(
                ws_msg=ws_msg,
                ws_connect=ws_connect,
                context={
                    'http_request': http_request,
                    'ws_connect': ws_connect,
                },
            )

            task = asyncio.create_task(coro)

            # To avoid a task disappearing mid execution:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return ws_connect

    async def _handle_ws_message(self,
                                 ws_msg: web_ws.WSMessage, *,
                                 ws_connect: web_ws.WebSocketResponse,
                                 context: dict) -> None:
        try:
            input_data = self._json_deserialize(ws_msg.data)
        except json.JSONDecodeError:
            logger.warning('Invalid JSON data: %s', ws_msg.data, exc_info=True)
            output_data = protocol.JSONRPCResponse(error=errors.ParseError(data={'details': 'Invalid JSON'}))
        else:
            if self._looks_like_response(input_data):
                if self._json_response_handler is not None:
                    await self._json_response_handler(
                        ws_connect=ws_connect,
                        ws_msg=ws_msg,
                        json_response=input_data,
                    )
                else:
                    logger.debug('WS server received response-shaped message but no handler is set.')

                return

            output_data = await self._process_input_data(input_data, context=context)  # type: ignore

        if output_data is None:
            return

        if ws_connect.closed:
            logger.warning('WebSocket connection closed by client.')
            return

        if isinstance(output_data, typing.Sequence):
            raw_output_data = tuple(response.dump() for response in output_data)
        else:
            raw_output_data = output_data.dump()  # type: ignore

        await ws_connect.send_str(self._json_serialize(raw_output_data))

    @staticmethod
    def _looks_like_response(data: typing.Any) -> bool:
        if isinstance(data, typing.Mapping):
            return 'method' not in data and 'id' in data and ('result' in data or 'error' in data)

        if isinstance(data, typing.Sequence) and data and isinstance(data[0], typing.Mapping):
            return 'method' not in data[0] and 'id' in data[0] and ('result' in data[0] or 'error' in data[0])

        return False
