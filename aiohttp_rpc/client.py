import abc
import asyncio
import json
import logging
import types
import typing
import uuid
from dataclasses import dataclass
from functools import partial

import aiohttp

from . import constants, errors, utils
from .protocol import JsonRpcRequest, JsonRpcResponse


__all__ = (
    'BaseJsonRpcClient',
    'JsonRpcClient',
    'WsJsonRpcClient',
    'UnlinkedResults',
)

logger = logging.getLogger(__name__)


@dataclass
class UnlinkedResults:
    data: list

    def compile(self) -> typing.Any:
        if not self.data:
            return None

        if len(self.data) == 1:
            return self.data[0]

        return self


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
        unlinked_results = UnlinkedResults(data=[])
        responses_map = {}

        for response in responses:
            if response.msg_id is None or response.msg_id is constants.NOTHING:
                unlinked_results.data.append(response.error or response.result)
                continue

            responses_map[response.msg_id] = response.error or response.result

        unlinked_results = unlinked_results.compile()
        result = []

        for request in requests:
            if request.msg_id is None or request.msg_id is constants.NOTHING:
                result.append(unlinked_results)
                continue

            result.append(responses_map.get(request.msg_id, unlinked_results))

        return result

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


class JsonRpcClient(BaseJsonRpcClient):
    url: str
    session: typing.Optional[aiohttp.ClientSession]
    request_kwargs: dict
    _is_outer_session: bool

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 **request_kwargs) -> None:
        self.url = url
        self.session = session
        self.request_kwargs = request_kwargs
        self._is_outer_session = session is not None

    async def connect(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(json_serialize=self.json_serialize)

    async def disconnect(self) -> None:
        if not self._is_outer_session:
            await self.session.close()

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        http_response = await self.session.post(self.url, json=data, **self.request_kwargs)

        try:
            json_response = await http_response.json()
        except aiohttp.ContentTypeError as e:
            raise errors.ParseError(utils.get_exc_message(e)) from e

        return json_response, {'http_response': http_response}


class WsJsonRpcClient(BaseJsonRpcClient):
    ws_connect = None
    notify_about_result: typing.Optional[typing.Callable] = None
    timeout: typing.Optional[int]
    ws_connect_kwargs: dict
    _pending: typing.Dict[typing.Any, asyncio.Future]
    _message_worker: typing.Optional[asyncio.Future] = None

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 timeout: typing.Optional[int] = 5,
                 **ws_connect_kwargs) -> None:
        self.url = url
        self.session = session
        self._is_outer_session = session is not None
        self._pending = {}
        self.timeout = timeout
        self.ws_connect_kwargs = ws_connect_kwargs

    async def connect(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(json_serialize=self.json_serialize)

        try:
            self.ws_connect = await self.session.ws_connect(self.url, **self.ws_connect_kwargs)
        except Exception:
            await self.disconnect()
            raise

        self._message_worker = asyncio.ensure_future(self._handle_ws_messages())

    async def disconnect(self) -> None:
        if self.ws_connect:
            await self.ws_connect.close()

        if not self._is_outer_session:
            await self.session.close()

        if self._message_worker:
            await self._message_worker

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        if without_response:
            await self.ws_connect.send_str(self.json_serialize(data))
            return None, None

        msg_ids = None

        if isinstance(data, dict):
            msg_ids = (data['id'],)
        elif isinstance(data, list):
            msg_ids = tuple(item['id'] for item in data)

        if not msg_ids:
            await self.ws_connect.send_str(self.json_serialize(data))
            return None, None

        future = asyncio.Future()

        for msg_id in msg_ids:
            self._pending[msg_id] = future

        await self.ws_connect.send_str(self.json_serialize(data))

        if self.timeout is not None:
            future = asyncio.wait_for(future, timeout=self.timeout)

        result = await future

        return result, None

    async def _handle_ws_messages(self) -> typing.NoReturn:
        while not self.ws_connect.closed:
            try:
                ws_msg = await self.ws_connect.receive()
                self._handle_ws_message(ws_msg)
            except asyncio.CancelledError as e:
                error = errors.ServerError(utils.get_exc_message(e)).with_traceback()
                self._notify_all_about_error(error)
                raise
            except Exception as e:
                logger.exception(e)

    def _handle_ws_message(self, ws_msg: aiohttp.WSMessage) -> None:
        if ws_msg.type != aiohttp.WSMsgType.text:
            return

        json_response = json.loads(ws_msg.data)

        if isinstance(json_response, dict) and 'id' in json_response:
            self._notify_about_result(json_response['id'], json_response)
            return

        if isinstance(json_response, list):
            self._notify_about_results(
                [
                    item['id']
                    for item in json_response
                    if isinstance(item, dict) and 'id' in item
                ],
                json_response,
            )

    def _notify_all_about_error(self, error: errors.JsonRpcError) -> None:
        for future in self._pending.values():
            future.set_exception(error)

        self._pending = {}

    def _notify_about_result(self, msg_id: typing.Any, json_response: dict) -> None:
        future = self._pending.pop(msg_id, None)

        if future:
            future.set_result(json_response)

    def _notify_about_results(self, msg_ids: list, json_response: list) -> None:
        is_processed = False

        for msg_id in msg_ids:
            future = self._pending.pop(msg_id, None)

            if future and not is_processed:
                future.set_result(json_response)
                is_processed = True
