import abc
import asyncio
import logging
import typing
from functools import partial

from .. import errors, protocol, typedefs, utils


__all__ = (
    'BaseJSONRPCServer',
)

logger = logging.getLogger(__name__)


class BaseJSONRPCServer(abc.ABC):
    methods: typing.MutableMapping[str, protocol.BaseJSONRPCMethod]
    middlewares: typing.Sequence[typing.Callable]
    _json_serialize: typedefs.JSONEncoderType
    _json_deserialize: typedefs.JSONDecoderType
    _middleware_chain: typedefs.UnboundSingleRequestProcessorType
    _max_batch: typing.Optional[int]

    def __init__(self, *,
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 json_deserialize: typedefs.JSONDecoderType = utils.json_deserialize,
                 middlewares: typing.Sequence = (),
                 methods: typing.Optional[typing.MutableMapping[str, protocol.BaseJSONRPCMethod]] = None,
                 max_batch: typing.Optional[int] = None) -> None:
        self.methods = methods or {}

        self.middlewares = middlewares
        self._load_middlewares()

        self._json_serialize = json_serialize
        self._json_deserialize = json_deserialize

        self._max_batch = max_batch

    def add_method(self,
                   method: typedefs.ServerMethodDescriptionType, *,
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
            raise errors.MethodNotFound()

        return await self.methods[method_name](args=args, kwargs=kwargs, extra_kwargs=extra_kwargs)

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
                for json_response in self._process_exceptions_if_have(json_responses)
                if json_response is not None  # Skip notifications.
            )

            return result or None

        if isinstance(data, typing.Mapping):
            try:
                return await self._process_single_json_request(data, context=context)
            except Exception:
                logger.exception('Unexpected error')
                return protocol.JSONRPCResponse(error=errors.InternalError())

        return protocol.JSONRPCResponse(
            error=errors.InvalidRequest(data={'details': 'Data must be a dict or a list.'}),
        )

    @staticmethod
    def _process_exceptions_if_have(values: typing.Iterable) -> typing.Iterable:
        for i, value in enumerate(values):
            if isinstance(value, Exception):
                # Use middlewares (`exception_middleware`) to process exceptions.
                logger.exception('Unexpected error', exc_info=value)
                yield protocol.JSONRPCResponse(error=errors.InternalError())
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
