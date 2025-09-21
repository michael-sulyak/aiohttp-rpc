import abc
import types
import typing

from .additional import JSONRPCClientMethods
from .. import errors, protocol, typedefs, utils


__all__ = (
    'BaseJSONRPCClient',
)


class BaseJSONRPCClient(abc.ABC):
    methods: JSONRPCClientMethods
    error_map: typing.Mapping[int, typing.Type[errors.JSONRPCError]]
    _json_serialize: typedefs.JSONEncoderType
    _json_deserialize: typedefs.JSONDecoderType

    def __init__(self, *,
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 json_deserialize: typedefs.JSONDecoderType = utils.json_deserialize,
                 error_map: typing.Mapping[int, typing.Type[errors.JSONRPCError]] = errors.DEFAULT_KNOWN_ERRORS_MAP,
                 ) -> None:
        self.methods = JSONRPCClientMethods(self)
        self.error_map = error_map
        self._json_serialize = json_serialize
        self._json_deserialize = json_deserialize

    async def __aenter__(self) -> 'BaseJSONRPCClient':
        await self.connect()
        return self

    async def __aexit__(self,
                        exc_type: typing.Optional[typing.Type[BaseException]],
                        exc_value: typing.Optional[BaseException],
                        traceback: typing.Optional[types.TracebackType]) -> None:
        await self.disconnect()

    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        pass

    async def call(self, method_name: str, *args, **kwargs) -> typing.Any:
        request = protocol.JSONRPCRequest(id=utils.get_random_id(), method_name=method_name, args=args, kwargs=kwargs)
        response = await self.direct_call(request)

        if response is None:
            raise errors.EmptyResponse()

        if response.error is not None:
            raise response.error

        return response.result

    async def notify(self, method_name: str, *args, **kwargs) -> None:
        request = protocol.JSONRPCRequest(method_name=method_name, args=args, kwargs=kwargs)
        await self.direct_call(request)

    async def batch(self,
                    *requests: protocol.JSONRPCRequest,
                    save_order: bool = True) -> typing.Sequence:
        batch_request = protocol.JSONRPCBatchRequest(requests=requests)

        batch_response = await self.direct_batch(batch_request)

        if batch_response is None:
            raise errors.EmptyResponse()

        if save_order:
            return utils.collect_batch_result(batch_request, batch_response)
        else:
            return tuple(
                response.result if response.error is None else response.error
                for response in batch_response.responses
            )

    async def batch_notify(self, *requests: protocol.JSONRPCRequest) -> None:
        batch_request = protocol.JSONRPCBatchRequest(requests=requests)
        await self.direct_batch(batch_request)

    async def direct_call(self,
                          request: protocol.JSONRPCRequest,
                          **kwargs) -> typing.Optional[protocol.JSONRPCResponse]:
        json_response, context = await self.send_json(
            request.dump(),
            ignore_response=request.is_notification,
            **kwargs,
        )

        if request.is_notification:
            return None

        response = protocol.JSONRPCResponse.load(
            json_response,
            error_map=self.error_map,
            context=context,
        )

        return response

    async def direct_batch(self,
                           batch_request: protocol.JSONRPCBatchRequest,
                           **kwargs) -> typing.Optional[protocol.JSONRPCBatchResponse]:
        if not batch_request.requests:
            raise errors.InvalidRequest('You can\'t send an empty batch request.')

        is_notification = batch_request.is_notification

        json_response, context = await self.send_json(
            batch_request.dump(),
            ignore_response=is_notification,
            **kwargs,
        )

        if is_notification:
            return None

        if not json_response:
            raise errors.ParseError('Server returned an empty batch response.')

        return protocol.JSONRPCBatchResponse.load(json_response, error_map=self.error_map)

    @abc.abstractmethod
    async def send_json(self,
                        data: typing.Any, *,
                        ignore_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        pass
