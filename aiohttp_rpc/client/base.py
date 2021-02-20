import abc
import types
import typing
from functools import partial

from .. import constants, errors, protocol, utils


__all__ = (
    'BaseJsonRpcClient',
)

MethodDescription = typing.Union[str, list, tuple, protocol.JsonRpcRequest]
MethodDescriptionList = typing.Iterable[typing.Union[MethodDescription, protocol.JsonRpcBatchRequest]]


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

    def __getattr__(self, method_name: str) -> typing.Callable:
        return partial(self.call, method_name)

    @abc.abstractmethod
    async def connect(self) -> None:
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        pass

    async def call(self, method_name: str, *args, **kwargs) -> typing.Any:
        request = protocol.JsonRpcRequest(id=utils.get_random_id(), method_name=method_name, args=args, kwargs=kwargs)
        response = await self.direct_call(request)

        if response.error not in constants.EMPTY_VALUES:
            raise response.error

        return response.result

    async def notify(self, method_name: str, *args, **kwargs) -> None:
        request = protocol.JsonRpcRequest(method_name=method_name, args=args, kwargs=kwargs)
        await self.direct_call(request)

    async def batch(self,
                    method_descriptions: MethodDescriptionList, *,
                    save_order: bool = True) -> typing.Any:
        if isinstance(method_descriptions, protocol.JsonRpcBatchRequest):
            batch_request = method_descriptions
        else:
            requests = [
                self._parse_method_description(method_description)
                for method_description in method_descriptions
            ]
            batch_request = protocol.JsonRpcBatchRequest(requests=requests)

        batch_response = await self.direct_batch(batch_request)

        if save_order:
            return self._collect_batch_result(batch_request, batch_response)
        else:
            return [
                response.result if response.error in constants.EMPTY_VALUES else response.error
                for response in batch_response.responses
            ]

    async def batch_notify(self, method_descriptions: MethodDescriptionList) -> None:
        if isinstance(method_descriptions, protocol.JsonRpcBatchRequest):
            batch_request = method_descriptions
        else:
            requests = [
                self._parse_method_description(method_description, is_notification=True)
                for method_description in method_descriptions
            ]
            batch_request = protocol.JsonRpcBatchRequest(requests=requests)

        await self.direct_batch(batch_request)

    async def direct_call(self,
                          request: protocol.JsonRpcRequest,
                          **kwargs) -> typing.Optional[protocol.JsonRpcResponse]:
        json_response, context = await self.send_json(
            request.to_dict(),
            without_response=request.is_notification,
            **kwargs,
        )

        if request.is_notification:
            return None

        response = protocol.JsonRpcResponse.from_dict(
            json_response,
            error_map=self.error_map,
            context=context,
        )

        return response

    async def direct_batch(self,
                           batch_request: protocol.JsonRpcBatchRequest,
                           **kwargs) -> typing.Optional[protocol.JsonRpcBatchResponse]:
        if not batch_request.requests:
            raise errors.InvalidRequest('You can not send an empty batch request.')

        is_notification = batch_request.is_notification
        json_response, context = await self.send_json(
            batch_request.to_list(),
            without_response=is_notification,
            **kwargs,
        )

        if is_notification:
            return None

        if not json_response:
            raise errors.ParseError('Server returned an empty batch response.')

        return protocol.JsonRpcBatchResponse.from_list(json_response)

    @abc.abstractmethod
    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
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

            if response.id in constants.EMPTY_VALUES:
                unlinked_results.add(value)
                continue

            if response.id in responses_map:
                if isinstance(responses_map[response.id], protocol.DuplicatedResults):
                    responses_map[response.id].add(value)
                else:
                    responses_map[response.id] = protocol.DuplicatedResults(data=[
                        responses_map[response.id],
                        value,
                    ])
            else:
                responses_map[response.id] = value

        if not unlinked_results:
            unlinked_results = None

        result = []

        for request in batch_request.requests:
            if request.is_notification:
                result.append(unlinked_results)
                continue

            result.append(responses_map.get(request.id, unlinked_results))

        return result

    @staticmethod
    def _parse_method_description(method_description: MethodDescription, *,
                                  is_notification: bool = False) -> protocol.JsonRpcRequest:
        if isinstance(method_description, protocol.JsonRpcRequest):
            return method_description

        request_id = constants.NOTHING if is_notification else utils.get_random_id()

        if isinstance(method_description, str):
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description,
            )

        if len(method_description) == 1:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
            )

        if len(method_description) == 2:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
                params=method_description[1],
            )

        if len(method_description) == 3:
            return protocol.JsonRpcRequest(
                id=request_id,
                method_name=method_description[0],
                args=method_description[1],
                kwargs=method_description[2],
            )

        raise errors.InvalidParams('Use string or list (length less than or equal to 3).')
