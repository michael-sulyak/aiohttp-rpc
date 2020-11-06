import abc
import types
import typing
from functools import partial

from .. import constants, errors, protocol, utils


__all__ = (
    'BaseJsonRpcClient',
)

MethodType = typing.Union[str, list, tuple, protocol.CalledJsonRpcMethod]


class BaseJsonRpcClient(abc.ABC):
    error_map: typing.Dict[int, errors.JsonRpcError] = {
        error.code: error
        for error in errors.DEFAULT_KNOWN_ERRORS
    }
    json_serialize: typing.Callable = utils.json_serialize

    async def __aenter__(self) -> 'BaseJsonRpcClient':
        await self.connect()
        return self

    async def __aexit__(self,
                        exc_type: typing.Optional[typing.Type[BaseException]],
                        exc_value: typing.Optional[BaseException],
                        traceback: typing.Optional[types.TracebackType]) -> None:
        await self.disconnect()

    def __getattr__(self, method) -> typing.Callable:
        return partial(self.call, method)

    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        pass

    async def call(self, method: str, *args, **kwargs) -> typing.Any:
        request = protocol.JsonRpcRequest(msg_id=utils.get_random_msg_id(), method=method, args=args, kwargs=kwargs)
        response = await self.direct_call(request)

        if response.error not in constants.EMPTY_VALUES:
            raise response.error

        return response.result

    async def notify(self, method: str, *args, **kwargs) -> None:
        request = protocol.JsonRpcRequest(method=method, args=args, kwargs=kwargs)
        await self.direct_call(request, without_response=True)

    async def batch(self,
                    methods: typing.Iterable[MethodType], *,
                    save_order: bool = True) -> typing.Any:
        requests = [self._parse_method(method) for method in methods]
        batch_request = protocol.JsonRpcBatchRequest(requests=requests)
        batch_response = await self.direct_batch(batch_request)

        if save_order:
            return self._collect_batch_result(batch_request, batch_response)
        else:
            return [
                response.result if response.error in constants.EMPTY_VALUES else response.error
                for response in batch_response.responses
            ]

    async def batch_notify(self, methods: typing.Iterable[MethodType]) -> None:
        requests = [self._parse_method(method, is_notification=True) for method in methods]
        batch_request = protocol.JsonRpcBatchRequest(requests=requests)
        await self.direct_batch(batch_request, without_response=True)

    async def direct_call(self,
                          request: protocol.JsonRpcRequest, *,
                          without_response: bool = False) -> typing.Optional[protocol.JsonRpcResponse]:
        json_response, context = await self.send_json(request.to_dict(), without_response=without_response)

        if without_response:
            return None

        response = protocol.JsonRpcResponse.from_dict(
            json_response,
            error_map=self.error_map,
            context=context,
        )

        return response

    async def direct_batch(self,
                           batch_request: protocol.JsonRpcBatchRequest, *,
                           without_response: bool = False) -> typing.Optional[protocol.JsonRpcBatchResponse]:
        if not batch_request.requests:
            raise errors.InvalidRequest('You can not send an empty batch request.')

        json_response, context = await self.send_json(batch_request.to_list(), without_response=without_response)

        if without_response:
            return None

        if not json_response:
            raise errors.ParseError('Server returned an empty batch response.')

        return protocol.JsonRpcBatchResponse.from_list(json_response)

    @abc.abstractmethod
    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        pass

    @staticmethod
    def _collect_batch_result(batch_request: protocol.JsonRpcBatchRequest,
                              batch_response: protocol.JsonRpcBatchResponse) -> list:
        unlinked_results = protocol.UnlinkedResults()
        responses_map = {}

        for response in batch_response.responses:
            if response.error in constants.EMPTY_VALUES:
                value = response.result
            else:
                value = response.error

            if response.msg_id in constants.EMPTY_VALUES:
                unlinked_results.add(value)
                continue

            if response.msg_id in responses_map:
                if isinstance(responses_map[response.msg_id], protocol.DuplicatedResults):
                    responses_map[response.msg_id].add(value)
                else:
                    responses_map[response.msg_id] = protocol.DuplicatedResults(data=[
                        responses_map[response.msg_id],
                        value,
                    ])

            responses_map[response.msg_id] = value

        if not unlinked_results:
            unlinked_results = None

        result = []

        for request in batch_request.requests:
            if request.is_notification:
                result.append(unlinked_results)
                continue

            result.append(responses_map.get(request.msg_id, unlinked_results))

        return result

    @staticmethod
    def _parse_method(method: MethodType, *, is_notification: bool = False) -> protocol.JsonRpcRequest:
        if isinstance(method, protocol.CalledJsonRpcMethod):
            called_method = method
        else:
            called_method = protocol.CalledJsonRpcMethod.from_params(method)
            called_method.is_notification = is_notification

        if called_method.msg_id in constants.EMPTY_VALUES and not called_method.is_notification:
            called_method.msg_id = utils.get_random_msg_id()

        return called_method.to_request()
