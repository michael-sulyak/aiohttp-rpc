import json
import typing

from aiohttp import web

from . import errors, middlewares as rpc_middleware, protocol, utils


__all__ = (
    'JsonRpcServer',
    'rpc_server',
)


class JsonRpcServer:
    methods: typing.Dict[str, protocol.JsonRpcMethod]
    middlewares: typing.Tuple[typing.Type[rpc_middleware.BaseJsonRpcMiddleware], ...]
    _json_serialize: typing.Callable
    _middleware_chain: typing.Callable

    def __init__(self, *,
                 json_serialize: typing.Callable = utils.json_serialize,
                 middlewares: typing.Iterable = (),
                 methods: typing.Optional[typing.Dict[str, protocol.JsonRpcMethod]] = None) -> None:
        if methods is None:
            methods = {'get_methods': protocol.JsonRpcMethod('', self.get_methods)}

        self.methods = methods

        self.middlewares = tuple(middlewares)
        self.load_middleware()

        self._json_serialize = json_serialize

    def load_middleware(self):
        self._middleware_chain = self._process_single_rpc_request

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

    async def handle_request(self, request: web.Request) -> web.Response:
        if request.method != 'POST':
            return web.HTTPMethodNotAllowed(method=request.method, allowed_methods=('POST',))

        try:
            input_data = await request.json()
        except json.JSONDecodeError as e:
            rpc_response = protocol.JsonRpcResponse(error=errors.ParseError(utils.exc_message(e)))
            return web.json_response(rpc_response.to_dict(), dumps=self._json_serialize)

        output_data = await self._process_input_data(input_data, http_request=request)

        return web.json_response(output_data, dumps=self._json_serialize)

    async def get_methods(self) -> dict:
        return {
            name: {
                'doc': method.func.__doc__,
                'args': method.supported_args,
                'kwargs': method.supported_kwargs,
            }
            for name, method in self.methods.items()
        }

    async def _process_input_data(self, data: dict, *, http_request: typing.Optional[web.Request] = None) -> typing.Any:
        if isinstance(data, list):
            result = []

            for raw_rcp_request in data:
                if isinstance(raw_rcp_request, dict):
                    result.append(await self._process_single_raw_rpc_request(
                        raw_rcp_request,
                        http_request=http_request,
                    ))
                else:
                    rpc_response = protocol.JsonRpcResponse(
                        error=errors.ParseError('Data must be a dict or an list.'),
                    )
                    result.append(rpc_response.to_dict())

            return result
        elif isinstance(data, dict):
            return await self._process_single_raw_rpc_request(data, http_request=http_request)
        else:
            rpc_response = protocol.JsonRpcResponse(error=errors.ParseError('Data must be a dict or an list.'))
            return rpc_response.to_dict()

    async def _process_single_raw_rpc_request(self,
                                              raw_rcp_request: dict, *,
                                              http_request: typing.Optional[web.Request] = None) -> dict:
        msg_id = raw_rcp_request.get('id')

        try:
            rpc_request = protocol.JsonRpcRequest.from_dict(raw_rcp_request, context={'http_request': http_request})
        except errors.JsonRpcError as e:
            rpc_response = protocol.JsonRpcResponse(msg_id=msg_id, error=e)
            return rpc_response.to_dict()

        rpc_response = await self._middleware_chain(rpc_request)
        return rpc_response.to_dict()

    async def _process_single_rpc_request(self, rpc_request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        result, error = None, None

        try:
            result = await self.call(
                rpc_request.method,
                args=rpc_request.args,
                kwargs=rpc_request.kwargs,
                extra_args=rpc_request.extra_args,
            )
        except errors.JsonRpcError as e:
            error = e

        rpc_response = protocol.JsonRpcResponse(
            msg_id=rpc_request.msg_id,
            jsonrpc=rpc_request.jsonrpc,
            result=result,
            error=error,
        )

        return rpc_response


rpc_server = JsonRpcServer(
    middlewares=rpc_middleware.DEFAULT_MIDDLEWARES,
)
