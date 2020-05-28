import abc
import asyncio
import json
import typing

import aiohttp
from aiohttp import web, web_ws

from . import constants, errors, middlewares as rpc_middleware, protocol, utils


__all__ = (
    'BaseJsonRpcServer',
    'JsonRpcServer',
    'WsJsonRpcServer',
    'rpc_server',
)


class BaseJsonRpcServer(abc.ABC):
    methods: typing.Dict[str, protocol.JsonRpcMethod]
    middlewares: typing.Tuple[typing.Type[rpc_middleware.BaseJsonRpcMiddleware], ...]
    json_serialize: typing.Callable
    _middleware_chain: typing.Callable

    def __init__(self, *,
                 json_serialize: typing.Callable = utils.json_serialize,
                 middlewares: typing.Iterable = (),
                 methods: typing.Optional[typing.Dict[str, protocol.JsonRpcMethod]] = None) -> None:
        if methods is None:
            methods = {'get_methods': protocol.JsonRpcMethod('', self.get_methods)}

        self.methods = methods

        self.middlewares = tuple(middlewares)
        self.load_middlewares()

        self.json_serialize = json_serialize

    def load_middlewares(self):
        self._middleware_chain = self._process_single_request

        for middleware_class in reversed(self.middlewares):
            if isinstance(middleware_class, (list, tuple,)):
                middleware_class, kwargs = middleware_class
                self._middleware_chain = middleware_class(server=self, get_response=self._middleware_chain, **kwargs)
                continue

            self._middleware_chain = middleware_class(server=self, get_response=self._middleware_chain)

    def add_method(self,
                   method: typing.Union[protocol.JsonRpcMethod, tuple, list, typing.Callable], *,
                   replace: bool = False) -> protocol.JsonRpcMethod:
        if not isinstance(method, protocol.JsonRpcMethod):
            if callable(method):
                method = protocol.JsonRpcMethod('', method)
            else:
                method = protocol.JsonRpcMethod(*method)

        if not replace and method.name in self.methods:
            raise errors.InvalidParams(f'Method {method.name} has already been added.')

        self.methods[method.name] = method

        return method

    def add_methods(self,
                    methods: typing.Iterable[typing.Union[protocol.JsonRpcMethod, tuple, list, typing.Callable]], *,
                    replace: bool = False) -> typing.List[protocol.JsonRpcMethod]:
        return [
            self.add_method(method, replace=replace)
            for method in methods
        ]

    async def call(self,
                   method: str, *,
                   args: typing.Optional[list] = None,
                   kwargs: typing.Optional[dict] = None,
                   extra_args: typing.Optional[dict] = None) -> typing.Any:
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        if method not in self.methods:
            raise errors.MethodNotFound

        return await self.methods[method](args=args, kwargs=kwargs, extra_args=extra_args)

    def get_methods(self) -> dict:
        return {
            name: {
                'doc': method.func.__doc__,
                'args': method.supported_args,
                'kwargs': method.supported_kwargs,
            }
            for name, method in self.methods.items()
        }

    async def _process_input_data(self,
                                  data: typing.Union[dict, list], *,
                                  http_request: typing.Optional[web.Request] = None) -> typing.Any:
        if isinstance(data, list):
            json_responses = await asyncio.gather(*(
                self._process_single_json_request(raw_rcp_request, http_request=http_request)
                for raw_rcp_request in data
            ), return_exceptions=True)

            for i, json_response in enumerate(json_responses):
                if isinstance(json_response, errors.JsonRpcError):
                    json_responses[i] = protocol.JsonRpcResponse(error=json_response)
                elif isinstance(json_response, Exception):
                    json_responses[i] = protocol.JsonRpcResponse(
                        error=errors.JsonRpcError(utils.get_exc_message(json_response)),
                    )

            return json_responses

        if isinstance(data, dict):
            return await self._process_single_json_request(data, http_request=http_request)

        response = protocol.JsonRpcResponse(error=errors.ParseError('Data must be a dict or an list.'))
        return response.to_dict()

    async def _process_single_json_request(self,
                                           json_request: dict, *,
                                           http_request: typing.Optional[web.Request] = None) -> dict:
        if not isinstance(json_request, dict):
            raise errors.ParseError('Data must be a dict or an list.')

        msg_id = json_request.get('id')

        try:
            request = protocol.JsonRpcRequest.from_dict(json_request, context={'http_request': http_request})
        except errors.JsonRpcError as e:
            response = protocol.JsonRpcResponse(msg_id=msg_id, error=e)
            return response.to_dict()

        response = await self._middleware_chain(request)
        return response.to_dict()

    async def _process_single_request(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        result, error = constants.NOTHING, constants.NOTHING

        try:
            result = await self.call(
                request.method,
                args=request.args,
                kwargs=request.kwargs,
                extra_args=request.extra_args,
            )
        except errors.JsonRpcError as e:
            error = e

        response = protocol.JsonRpcResponse(
            msg_id=request.msg_id,
            jsonrpc=request.jsonrpc,
            result=result,
            error=error,
        )

        return response


class JsonRpcServer(BaseJsonRpcServer):
    async def handle_http_request(self, http_request: web.Request) -> web.Response:
        if http_request.method != 'POST':
            return web.HTTPMethodNotAllowed(method=http_request.method, allowed_methods=('POST',))

        try:
            input_data = await http_request.json()
        except json.JSONDecodeError as e:
            response = protocol.JsonRpcResponse(error=errors.ParseError(utils.get_exc_message(e)))
            return web.json_response(response.to_dict(), dumps=self.json_serialize)

        output_data = await self._process_input_data(input_data, http_request=http_request)

        return web.json_response(output_data, dumps=self.json_serialize)


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

            if ws_msg.type != aiohttp.WSMsgType.TEXT:
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


rpc_server = JsonRpcServer(
    middlewares=rpc_middleware.DEFAULT_MIDDLEWARES,
)
