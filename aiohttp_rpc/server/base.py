import abc
import asyncio
import typing
from functools import partial

from .. import errors, protocol, typedefs, utils


__all__ = (
    'BaseJSONRPCServer',
)


class BaseJSONRPCServer(abc.ABC):
    methods: typing.MutableMapping[str, protocol.BaseJSONRPCMethod]
    middlewares: typing.Sequence[typing.Callable]
    json_serialize: typedefs.UnboundJSONEncoderType
    _middleware_chain: typedefs.UnboundSingleRequestProcessorType
    _max_batch: typing.Optional[int]
    _max_payload_bytes: typing.Optional[int]

    def __init__(self, *,
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 middlewares: typing.Sequence = (),
                 methods: typing.Optional[typing.MutableMapping[str, protocol.BaseJSONRPCMethod]] = None,
                 max_batch: typing.Optional[int] = None,
                 max_payload_bytes: typing.Optional[int] = 1_048_576) -> None:
        self.methods = methods or {}

        self.middlewares = middlewares
        self._load_middlewares()

        self.json_serialize = json_serialize  # type: ignore

        self._max_batch = max_batch
        self._max_payload_bytes = max_payload_bytes

    def add_method(self,
                   method: typing.Union[typedefs.ServerMethodDescriptionType], *,
                   replace: bool = False) -> protocol.BaseJSONRPCMethod:
        if not isinstance(method, protocol.BaseJSONRPCMethod):
            method = protocol.JSONRPCMethod(method)

        if not replace and method.name in self.methods:
            raise errors.InvalidParams(data={'details': f'Method {method.name} has already been added.'})

        self.methods[method.name] = method

        return method

    def add_methods(self,
                    methods: typing.Sequence[typedefs.ServerMethodDescriptionType], *,
                    replace: bool = False) -> typing.Tuple[protocol.BaseJSONRPCMethod, ...]:
        return tuple(
            self.add_method(method, replace=replace)
            for method in methods
        )

    async def call(self,
                   method_name: str, *,
                   args: typing.Optional[typing.Sequence] = None,
                   kwargs: typing.Optional[typing.Mapping] = None,
                   extra_kwargs: typing.Optional[typing.Mapping] = None) -> typing.Any:
        if args is None:
            args = ()

        if kwargs is None:
            kwargs = {}

        if method_name not in self.methods:
            raise errors.MethodNotFound

        return await self.methods[method_name](args=args, kwargs=kwargs, extra_kwargs=extra_kwargs)

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

    def add_introspection(self) -> None:
        self.add_methods((self.get_method, self.get_methods,))

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
    ) -> typing.Optional[typing.Union[protocol.JSONRPCResponse, typing.Tuple[protocol.JSONRPCResponse, ...]]]:
        if isinstance(data, typing.Sequence) and not isinstance(data, (str, bytes,)):
            if not data:
                return protocol.JSONRPCResponse(error=errors.InvalidRequest())

            if self._max_batch is not None and len(data) > self._max_batch:
                return protocol.JSONRPCResponse(
                    error=errors.InvalidRequest(data={'details': 'Batch too large.'}),
                )

            json_responses = await asyncio.gather(
                *(
                    self._process_single_json_request(raw_rpc_request, context=context)
                    for raw_rpc_request in data
                ),
                return_exceptions=True,
            )

            result = tuple(
                json_response
                for json_response in self._raise_exception_if_have(json_responses)
                if json_response is not None  # Skip notifications.
            )

            return result or None

        if isinstance(data, typing.Mapping):
            return await self._process_single_json_request(data, context=context)

        return protocol.JSONRPCResponse(
            error=errors.InvalidRequest(data={'details': 'Data must be a dict or a list.'}),
        )

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
                                           ) -> typing.Optional[protocol.JSONRPCResponse]:
        if not isinstance(json_request, typing.Mapping):
            return protocol.JSONRPCResponse(
                error=errors.InvalidRequest(data={'details': 'Data must be a dict.'}),
            )

        try:
            request = protocol.JSONRPCRequest.load(json_request, context=context)
        except errors.JSONRPCError as e:
            return protocol.JSONRPCResponse(id=json_request.get('id'), error=e)

        response = await self._middleware_chain(request)  # type: ignore

        if response.is_notification:
            return None

        return response

    async def _process_single_request(self, request: protocol.JSONRPCRequest) -> protocol.JSONRPCResponse:
        result, error = None, None

        try:
            result = await self.call(
                request.method_name,
                args=request.args,
                kwargs=request.kwargs,
                extra_kwargs=request.extra_kwargs,
            )
        except errors.JSONRPCError as e:
            error = e

        response = protocol.JSONRPCResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            result=result,
            error=error,
        )

        return response
