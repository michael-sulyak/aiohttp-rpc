import abc
import types
import typing
import uuid
from dataclasses import dataclass
from functools import partial

from .. import constants, errors, utils
from ..protocol import JsonRpcRequest, JsonRpcResponse


__all__ = (
    'BaseJsonRpcClient',
    'UnlinkedResults',
)


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

    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        pass

    async def call(self, method: str, *args, **kwargs) -> typing.Any:
        request = JsonRpcRequest(msg_id=str(uuid.uuid4()), method=method, args=args, kwargs=kwargs)
        response = await self.direct_call(request)

        if response.error:
            raise response.error

        return response.result

    async def notify(self, method: str, *args, **kwargs) -> None:
        request = JsonRpcRequest(method=method, args=args, kwargs=kwargs)
        await self.send_json(request.to_dict(), without_response=True)

    async def batch(self, methods: typing.Iterable[typing.Union[str, list, tuple]]) -> typing.Any:
        requests = [self._parse_batch_method(method) for method in methods]
        responses = await self.direct_batch(requests)
        return self._collect_batch_result(requests, responses)

    async def batch_notify(self, methods: typing.Iterable[typing.Union[str, list, tuple]]) -> None:
        requests = [self._parse_batch_method(method, is_notification=True) for method in methods]
        data = [request.to_dict() for request in requests]
        await self.send_json(data, without_response=True)

    async def direct_call(self, request: JsonRpcRequest) -> JsonRpcResponse:
        json_response, context = await self.send_json(request.to_dict())
        response = JsonRpcResponse.from_dict(
            json_response,
            error_map=self.error_map,
            context=context,
        )
        return response

    async def direct_batch(self, requests: typing.List[JsonRpcRequest]) -> typing.List[JsonRpcResponse]:
        data = [request.to_dict() for request in requests]
        json_response, context = await self.send_json(data)

        return [
            JsonRpcResponse.from_dict(item, error_map=self.error_map, context=context)
            for item in json_response
        ]

    @abc.abstractmethod
    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        pass

    def __getattr__(self, method) -> typing.Callable:
        return partial(self.call, method)

    @staticmethod
    def _collect_batch_result(requests: typing.List[JsonRpcRequest], responses: typing.List[JsonRpcResponse]) -> list:
        unlinked_results = UnlinkedResults(data=[])
        responses_map = {}

        for response in responses:
            value = response.error or response.result

            if response.msg_id in constants.EMPTY_VALUES:
                unlinked_results.data.append(value)
                continue

            responses_map[response.msg_id] = value

        unlinked_results = unlinked_results.compile()
        result = []

        for request in requests:
            if request.msg_id in constants.EMPTY_VALUES:
                result.append(unlinked_results)
                continue

            result.append(responses_map.get(request.msg_id, unlinked_results))

        return result

    @staticmethod
    def _parse_batch_method(batch_method: typing.Union[str, list, tuple], *,
                            is_notification: bool = False) -> JsonRpcRequest:
        msg_id = constants.NOTHING if is_notification else str(uuid.uuid4())

        if isinstance(batch_method, str):
            return JsonRpcRequest(msg_id=msg_id, method=batch_method)

        if len(batch_method) == 1:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0])

        if len(batch_method) == 2:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0], params=batch_method[1])

        if len(batch_method) == 3:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0], args=batch_method[1], kwargs=batch_method[2])

        raise errors.InvalidParams('Use string or list (length less than or equal to 3).')


@dataclass
class UnlinkedResults:
    data: list

    def compile(self) -> typing.Any:
        if not self.data:
            return None

        if len(self.data) == 1:
            return self.data[0]

        return self
