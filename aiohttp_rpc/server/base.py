import abc
import asyncio
import typing
from functools import partial

from .. import constants, errors, protocol, utils


__all__ = (
    'BaseJsonRpcServer',
)


class BaseJsonRpcServer(abc.ABC):
    methods: typing.Dict[str, protocol.BaseJsonRpcMethod]
    middlewares: typing.Tuple[typing.Callable, ...]
    json_serialize: typing.Callable
    _middleware_chain: typing.Callable

    def __init__(self, *,
                 json_serialize: typing.Callable = utils.json_serialize,
                 middlewares: typing.Iterable = (),
                 methods: typing.Optional[typing.Dict[str, protocol.BaseJsonRpcMethod]] = None) -> None:
        if methods is None:
            methods = {
                'get_method': protocol.JsonRpcMethod('', self.get_method),
                'get_methods': protocol.JsonRpcMethod('', self.get_methods),
            }

        self.methods = methods

        self.middlewares = tuple(middlewares)
        self.load_middlewares()

        self.json_serialize = json_serialize

    def load_middlewares(self) -> None:
        self._middleware_chain = self._process_single_request

        for middleware in reversed(self.middlewares):
            self._middleware_chain = partial(middleware, handler=self._middleware_chain)

    def add_method(self,
                   method: typing.Union[protocol.BaseJsonRpcMethod, tuple, list, typing.Callable], *,
                   replace: bool = False) -> protocol.BaseJsonRpcMethod:
        if not isinstance(method, protocol.BaseJsonRpcMethod):
            if callable(method):
                method = protocol.JsonRpcMethod('', method)
            else:
                method = protocol.JsonRpcMethod(*method)

        if not replace and method.name in self.methods:
            raise errors.InvalidParams(f'Method {method.name} has already been added.')

        self.methods[method.name] = method

        return method

    def add_methods(self,
                    methods: typing.Iterable[typing.Union[protocol.BaseJsonRpcMethod, tuple, list, typing.Callable]], *,
                    replace: bool = False) -> typing.List[protocol.BaseJsonRpcMethod]:
        return [
            self.add_method(method, replace=replace)
            for method in methods
        ]

    async def call(self,
                   method_name: str, *,
                   args: typing.Optional[list] = None,
                   kwargs: typing.Optional[dict] = None,
                   extra_args: typing.Optional[dict] = None) -> typing.Any:
        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        if method_name not in self.methods:
            raise errors.MethodNotFound

        return await self.methods[method_name](args=args, kwargs=kwargs, extra_args=extra_args)

    def get_methods(self) -> dict:
        return {
            name: {
                'doc': method.func.__doc__,
                'args': method.supported_args,
                'kwargs': method.supported_kwargs,
            }
            for name, method in self.methods.items()
        }

    def get_method(self, name: str) -> typing.Optional[dict]:
        method = self.methods.get(name)

        if not method:
            return None

        return {
            'doc': method.func.__doc__,
            'args': method.supported_args,
            'kwargs': method.supported_kwargs,
        }

    async def _process_input_data(self,
                                  data: typing.Union[dict, list], *,
                                  context: typing.Dict[str, typing.Any],
                                  ) -> typing.Optional[typing.Union[dict, typing.List[dict]]]:
        if isinstance(data, list):
            if not data:
                return protocol.JsonRpcResponse(error=errors.InvalidRequest()).to_dict()

            coros = (
                self._process_single_json_request(raw_rcp_request, context=context)
                for raw_rcp_request in data
            )
            json_responses = await asyncio.gather(*coros, return_exceptions=True)
            self._prepare_exceptions(json_responses)
            result = [json_response for json_response in json_responses if json_response is not None]
            return result if result else None

        if isinstance(data, dict):
            return await self._process_single_json_request(data, context=context)

        response = protocol.JsonRpcResponse(error=errors.InvalidRequest('Data must be a dict or an list.'))
        return response.to_dict()

    @staticmethod
    def _prepare_exceptions(values: list) -> None:
        for i, value in enumerate(values):
            if isinstance(value, errors.JsonRpcError):
                values[i] = protocol.JsonRpcResponse(error=value)
            elif isinstance(value, Exception):
                raise value

    async def _process_single_json_request(self,
                                           json_request: dict, *,
                                           context: typing.Dict[str, typing.Any]) -> typing.Optional[dict]:
        try:
            if not isinstance(json_request, dict):
                raise errors.InvalidRequest('Data must be a dict.')

            request = protocol.JsonRpcRequest.from_dict(json_request, context=context)
        except errors.JsonRpcError as e:
            request_id = json_request.get('id', constants.NOTHING) if isinstance(json_request, dict) else constants.NOTHING
            response = protocol.JsonRpcResponse(id=request_id, error=e)
            return response.to_dict()

        response = await self._middleware_chain(request)

        if response.is_notification:
            return None

        return response.to_dict()

    async def _process_single_request(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        result, error = constants.NOTHING, constants.NOTHING

        try:
            result = await self.call(
                request.method_name,
                args=request.args,
                kwargs=request.kwargs,
                extra_args=request.extra_args,
            )
        except errors.JsonRpcError as e:
            error = e

        response = protocol.JsonRpcResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            result=result,
            error=error,
        )

        return response
