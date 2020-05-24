import json
import typing
import uuid
from functools import partial

import aiohttp

from . import exceptions
from .protocol import JsonRpcRequest, JsonRpcResponse


class JsonRpcClient:
    _json_serializer = partial(json.dumps, default=lambda x: repr(x))
    _session: typing.Optional[aiohttp.ClientSession] = None
    _is_outer_session: bool
    _url: str = None
    _error_map: typing.Dict[int, exceptions.JsonRpcError] = {
        error.code: error
        for error in exceptions.DEFAULT_KNOWN_ERRORS
    }

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 known_errors: typing.Optional[typing.Iterable] = None,
                 json_serializer: typing.Any = None) -> None:
        self._url = url
        self._session = session
        self._is_outer_session = bool(session)

        if known_errors is not None:
            self._error_map = {error.code: error for error in known_errors}

        if json_serializer is not None:
            self._json_serializer = json_serializer

    def __getattr__(self, method) -> typing.Callable:
        return partial(self.call, method)

    async def call(self, method: str, *args, **kwargs) -> typing.Any:
        rpc_request = JsonRpcRequest(msg_id=str(uuid.uuid4()), method=method, args=args, kwargs=kwargs)
        rpc_response = await self.raw_call(rpc_request)

        if rpc_response.error:
            raise rpc_response.error

        return rpc_response.result

    async def batch(self, methods: typing.Iterable) -> typing.Any:
        messages = []

        for method in methods:
            msg_id = str(uuid.uuid4())

            if isinstance(method, str):
                rpc_request = JsonRpcRequest(msg_id=msg_id, method=method)
            elif len(method) == 1:
                rpc_request = JsonRpcRequest(msg_id=msg_id, method=method[0])
            elif len(method) == 2:
                rpc_request = JsonRpcRequest(msg_id=msg_id, method=method[0], params=method[1])
            elif len(method) == 3:
                rpc_request = JsonRpcRequest(msg_id=msg_id, method=method[0], args=method[1], kwargs=method[2])
            else:
                raise exceptions.InvalidParams

            messages.append(rpc_request.to_dict())

        raw_response = await self.send_raw_data(messages)
        raw_rpc_responses = await raw_response.json()

        result = []

        for raw_rpc_response in raw_rpc_responses:
            rpc_response = JsonRpcResponse.from_dict(raw_rpc_response, error_map=self._error_map)

            if rpc_response.error:
                result.append(rpc_response.error)
            else:
                result.append(rpc_response.result)

        return result

    async def raw_call(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        raw_response = await self.send_raw_data(rpc_request.to_dict())
        data = await raw_response.json()
        rpc_response = JsonRpcResponse.from_dict(data, error_map=self._error_map)
        return rpc_response

    async def send_raw_data(self, data: typing.Any) -> typing.Any:
        return await self._session.post(self._url, json=data)

    async def __aenter__(self):
        if not self._session:
            self._session = aiohttp.ClientSession(json_serialize=self._json_serializer)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._is_outer_session:
            await self._session.close()
