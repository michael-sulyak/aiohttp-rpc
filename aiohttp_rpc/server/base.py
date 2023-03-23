import abc
import asyncio
import typing
from functools import partial

from .. import errors, protocol, typedefs, utils


__all__ = (
    'BaseJsonRpcServer',
)


class BaseJsonRpcServer(abc.ABC):
    methods: typing.MutableMapping[str, protocol.BaseJsonRpcMethod]
    middlewares: typing.Sequence[typing.Callable]
    json_serialize: typedefs.UnboundJSONEncoderType
    _middleware_chain: typing.ClassVar[typedefs.UnboundSingleRequestProcessorType]

    def __init__(self, *,
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 middlewares: typing.Sequence = (),
                 methods: typing.Optional[typing.MutableMapping[str, protocol.BaseJsonRpcMethod]] = None) -> None:
        if methods is None:
            methods = {
                'get_method': protocol.JsonRpcMethod(self.get_method),
                'get_methods': protocol.JsonRpcMethod(self.get_methods),
            }

        self.methods = methods

        self.middlewares = middlewares
        self._load_middlewares()

        self.json_serialize = json_serialize  # type: ignore

    def add_method(self,
                   method: typing.Union[typedefs.ServerMethodDescriptionType], *,
                   replace: bool = False) -> protocol.BaseJsonRpcMethod:
        if not isinstance(method, protocol.BaseJsonRpcMethod):
            method = protocol.JsonRpcMethod(method)

        if not replace and method.name in self.methods:
            raise errors.InvalidParams(f'Method {method.name} has already been added.')

        self.methods[method.name] = method

        return method

    def add_methods(self,
                    methods: typing.Sequence[typedefs.ServerMethodDescriptionType], *,
                    replace: bool = False) -> typing.Tuple[protocol.BaseJsonRpcMethod, ...]:
        return tuple(
            self.add_method(method, replace=replace)
            for method in methods
        )

    async def call(self,
                   method_name: str, *,
                   args: typing.Optional[typing.Sequence] = None,
                   kwargs: typing.Optional[typing.Mapping] = None,
                   extra_args: typing.Optional[typing.Mapping] = None) -> typing.Any:
        if args is None:
            args = ()

        if kwargs is None:
            kwargs = {}

        if method_name not in self.methods:
            raise errors.MethodNotFound

        return await self.methods[method_name](args=args, kwargs=kwargs, extra_args=extra_args)

    def get_methods(self) -> typing.Mapping[str, typing.Mapping[str, typing.Any]]:
        return {
            name: {
                'doc': method.doc,
                'args': method.supported_args,
                'kwargs': method.supported_kwargs,
            }
            for name, method in self.methods.items()
        }

    def get_method(self, name: str) -> typing.Optional[typing.Mapping[str, typing.Any]]:
        method = self.methods.get(name)

        if not method:
            return None

        return {
            'doc': method.doc,
            'args': method.supported_args,
            'kwargs': method.supported_kwargs,
        }

    def _load_middlewares(self) -> None:
        self._middleware_chain = self._process_single_request  # type: ignore

        for middleware in reversed(self.middlewares):
            self._middleware_chain: typedefs.SingleRequestProcessorType = partial(  # type: ignore
                middleware,
                handler=self._middleware_chain,
            )

    async def _process_input_data(
            self,
            data: typing.Any, *,
            context: typing.MutableMapping[str, typing.Any],
    ) -> typing.Optional[typing.Union[typing.Mapping, typing.Tuple[typing.Mapping, ...]]]:
        if isinstance(data, typing.Sequence):
            if not data:
                return protocol.JsonRpcResponse(error=errors.InvalidRequest()).dump()

            json_responses = await asyncio.gather(
                *(
                    self._process_single_json_request(raw_rcp_request, context=context)
                    for raw_rcp_request in data
                ),
                return_exceptions=True,
            )

            result = tuple(
                json_response
                for json_response in self._raise_exception_if_have(json_responses)
                if json_response is not None  # Skip notifications.
            )

            return result if result else None

        if isinstance(data, typing.Mapping):
            return await self._process_single_json_request(data, context=context)

        response = protocol.JsonRpcResponse(error=errors.InvalidRequest('Data must be a dict or an list.'))
        return response.dump()

    @staticmethod
    def _raise_exception_if_have(values: typing.Iterable) -> typing.Iterable:
        for i, value in enumerate(values):
            if isinstance(value, Exception):
                # Use middlewares (`exception_middleware`) to process exceptions.
                raise value
            else:
                yield value

    async def _process_single_json_request(self,
                                           json_request: typing.Any, *,
                                           context: typing.MutableMapping[str, typing.Any],
                                           ) -> typing.Optional[typing.Mapping]:
        if not isinstance(json_request, typing.Mapping):
            return protocol.JsonRpcResponse(error=errors.InvalidRequest('Data must be a dict.')).dump()

        try:
            request = protocol.JsonRpcRequest.load(json_request, context=context)
        except errors.JsonRpcError as e:
            return protocol.JsonRpcResponse(id=json_request.get('id'), error=e).dump()

        response = await self._middleware_chain(request)

        if response.is_notification:
            return None

        return response.dump()

    async def _process_single_request(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        result, error = None, None

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
