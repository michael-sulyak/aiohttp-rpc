import aiohttp_rpc
from tests import utils


async def test_middleware(aiohttp_client):
    def method():
        return 'ok'

    async def test_middleware(request, handler):
        request.method_name = 'method'
        response = await handler(request)
        response.result += '!'
        return response

    rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=(test_middleware,))
    rpc_server.add_method(method)

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.call('my_method') == 'ok!'
