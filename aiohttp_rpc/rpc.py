import json
import logging
import typing
from functools import partial

from aiohttp import web

from . import exceptions
from .protocol import JsonRpcMethod, JsonRpcRequest, JsonRpcResponse

api_routes = web.RouteTableDef()


class JsonRpcManager:
    methods: typing.Dict[str, JsonRpcMethod]
    dumps = partial(json.dumps, default=lambda x: repr(x))

    def __init__(self) -> None:
        self.methods = {
            'get_methods': JsonRpcMethod('', self.get_methods),
        }

    def add_method(self, method: typing.Union[JsonRpcMethod, tuple, list]) -> None:
        if isinstance(method, (tuple, list,)):
            method = JsonRpcMethod(*method)

        self.methods[method.name] = method

    def add_methods(self, methods: typing.Iterable[typing.Union[JsonRpcMethod, tuple, list]]) -> None:
        for method in methods:
            self.add_method(method)

    async def call(self, rpc_request: JsonRpcRequest) -> typing.Any:
        if rpc_request.method not in self.methods:
            raise exceptions.MethodNotFound

        return await self.methods[rpc_request.method](
            rpc_request.args,
            rpc_request.kwargs,
            extra_kwargs={
                'rpc_request': rpc_request,
                'request': rpc_request.http_request,
            },
        )

    async def handle_request(self, request: web.Request) -> web.Response:
        if request.method != 'POST':
            return web.Response(status=405)

        try:
            input_data = await request.json()
        except json.JSONDecodeError:
            rpc_response = JsonRpcResponse(error=exceptions.ParseError())
            return web.json_response(rpc_response.to_dict(), dumps=self.dumps)

        output_data = await self.process_input_data(input_data, http_request=request)

        return web.json_response(output_data, dumps=self.dumps)

    async def process_input_data(self, data: dict, *, http_request: typing.Optional[web.Request] = None) -> typing.Any:
        if isinstance(data, list):
            raw_rcp_requests = data
        else:
            raw_rcp_requests = [data]

        result = []

        for raw_rcp_request in raw_rcp_requests:
            msg_id = data.get('id')
            params = raw_rcp_request.get('params')
            jsonrpc = raw_rcp_request.get('jsonrpc', '2.0')

            try:
                method = raw_rcp_request['method']
            except KeyError:
                rpc_response = JsonRpcResponse(msg_id=msg_id, error=exceptions.InvalidParams())
                return web.json_response(rpc_response.to_dict(), dumps=self.dumps)

            rpc_request = JsonRpcRequest(
                msg_id=msg_id,
                method=method,
                params=params,
                jsonrpc=jsonrpc,
                http_request=http_request,
            )

            rpc_response = await self.process_rpc_request(rpc_request)
            result.append(rpc_response.to_dict())

        if isinstance(data, dict):
            result = result[0]

        return result

    async def process_rpc_request(self, rpc_request: JsonRpcRequest) -> JsonRpcResponse:
        rpc_response = JsonRpcResponse(
            msg_id=rpc_request.msg_id,
            jsonrpc=rpc_request.jsonrpc,
        )

        try:
            rpc_response.result = await default_rpc_manager.call(rpc_request)
        except exceptions.JsonRpcError as e:
            rpc_response.error = e
        except Exception as e:
            logging.warning(e, exc_info=True)
            rpc_response.error = exceptions.InternalError(data=repr(e))

        return rpc_response

    async def get_methods(self) -> dict:
        result = {}

        for method in self.methods.values():
            result[method.name] = {
                'args': method.supported_args,
                'kwargs': method.supported_kwargs,
            }

        return result


default_rpc_manager = JsonRpcManager()

