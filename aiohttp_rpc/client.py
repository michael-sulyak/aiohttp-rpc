import types
import typing
import uuid
from functools import partial

import aiohttp

from . import errors, utils
from .protocol import JsonRpcRequest, JsonRpcResponse


__all__ = (
    'JsonRpcClient',
)


class JsonRpcClient:
    url: str
    session: typing.Optional[aiohttp.ClientSession]
    _json_serialize: typing.Callable
    _is_outer_session: bool
    _error_map: typing.Dict[int, errors.JsonRpcError] = {
        error.code: error
        for error in errors.DEFAULT_KNOWN_ERRORS
    }

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 known_errors: typing.Optional[typing.Iterable] = None,
                 json_serialize: typing.Callable = utils.json_serialize) -> None:
        self.url = url
        self.session = session
        self._is_outer_session = session is not None
        self._json_serialize = json_serialize

        if known_errors is not None:
            self._error_map = {error.code: error for error in known_errors}

    def __getattr__(self, method) -> typing.Callable:
        return partial(self.call, method)

    async def call(self, method: str, *args, **kwargs) -> typing.Any:
        rpc_request = JsonRpcRequest(msg_id=str(uuid.uuid4()), method=method, args=args, kwargs=kwargs)
        rpc_response = await self.direct_call(rpc_request)

        if rpc_response.error:
            raise rpc_response.error

        return rpc_response.result

    async def batch(self, methods: typing.Iterable[typing.Union[str, list, tuple]]) -> typing.Any:
        rpc_requests = []

        for method in methods:
            rpc_request = self._parse_batch_method(method)
            rpc_requests.append(rpc_request)

        rpc_responses = await self.direct_batch(rpc_requests)

        return [
            rpc_response.error if rpc_response.error else rpc_response.result
            for rpc_response in rpc_responses
        ]

    async def direct_call(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        http_response, json_response = await self.send_json(rpc_request.to_dict())
        rpc_response = JsonRpcResponse.from_dict(
            json_response,
            error_map=self._error_map,
            context={'http_response': http_response},
        )
        return rpc_response

    async def direct_batch(self, rpc_requests: typing.List[JsonRpcRequest]) -> typing.List[JsonRpcResponse]:
        data = [rpc_request.to_dict() for rpc_request in rpc_requests]
        http_response, json_response = await self.send_json(data)

        return [
            JsonRpcResponse.from_dict(item, error_map=self._error_map, context={'http_response': http_response})
            for item in json_response
        ]

    async def send_json(self, data: typing.Any) -> typing.Tuple[aiohttp.ClientResponse, typing.Any]:
        http_response = await self.session.post(self.url, json=data)
        json_response = await http_response.json()
        return http_response, json_response

    async def __aenter__(self) -> 'JsonRpcClient':
        if not self.session:
            self.session = aiohttp.ClientSession(json_serialize=self._json_serialize)

        return self

    async def __aexit__(self,
                        exc_type: typing.Optional[typing.Type[BaseException]],
                        exc_value: typing.Optional[BaseException],
                        traceback: typing.Optional[types.TracebackType]) -> None:
        if not self._is_outer_session:
            await self.session.close()

    @staticmethod
    def _parse_batch_method(batch_method: typing.Union[str, list, tuple]) -> JsonRpcRequest:
        msg_id = str(uuid.uuid4())

        if isinstance(batch_method, str):
            return JsonRpcRequest(msg_id=msg_id, method=batch_method)

        if len(batch_method) == 1:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0])

        if len(batch_method) == 2:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0], params=batch_method[1])

        if len(batch_method) == 3:
            return JsonRpcRequest(msg_id=msg_id, method=batch_method[0], args=batch_method[1], kwargs=batch_method[2])

        raise errors.InvalidParams('Use string or list (length less than or equal to 3).')
