import asyncio
import datetime

import aiohttp_rpc
from tests import utils


async def test_args(aiohttp_client):
    def method(a=1):
        return [1, 2, a]

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(method)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == [1, 2, 1]
        assert await rpc.call('method', 1) == [1, 2, 1]


async def test_batch(aiohttp_client):
    def method_1(a=1):
        return [1, a]

    def method_2():
        return 1

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_methods((method_1, method_2,))

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.batch(('method_1', 'method_2',)) == ([1, 1], 1,)
        assert await rpc.batch((('method_1', 4), ('method_1', [], {'a': 5},),)) == ([1, 4], [1, 5],)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.batch_notify(('method_1', 'method_2',)) is None
        assert await rpc.batch_notify((('method_1', 4), ('method_1', [], {'a': 5},),)) is None


async def test_several_requests(aiohttp_client):
    async def method(a):
        await asyncio.sleep(0.2)
        return a

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(method)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        started_at = datetime.datetime.now()

        result = await asyncio.gather(*(
            rpc.call('method', i)
            for i in range(10)
        ))

        finished_at = datetime.datetime.now()

        assert finished_at - started_at < datetime.timedelta(seconds=1)
        assert result == list(range(10))


async def test_ws_client_for_server_response(aiohttp_client, mocker):
    async def method(rpc_ws_client: aiohttp_rpc.WsJsonRpcClient):
        await rpc_ws_client.notify('ping')
        await rpc_ws_client.notify('ping')
        await rpc_ws_client.notify('ping')

    rpc_server = aiohttp_rpc.WsJsonRpcServer(
        middlewares=[
            *aiohttp_rpc.middlewares.DEFAULT_MIDDLEWARES,
            aiohttp_rpc.middlewares.ws_client_for_server_response,
        ],
    )
    rpc_server.add_method(method)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    future = asyncio.Future()

    results = []

    def json_request_handler(*, ws_connect, ws_msg, json_request):
        results.append(json_request)

        if len(results) == 3:
            future.set_result(results)

    async with aiohttp_rpc.WsJsonRpcClient(
            '/rpc',
            session=client,
            json_request_handler=json_request_handler,
    ) as rpc:
        json_request_handler = mocker.patch.object(rpc, '_json_request_handler', side_effect=rpc._json_request_handler)
        await rpc.method()

        await asyncio.wait_for(future, timeout=3)
        assert json_request_handler.call_count == 3
        assert results[0]['method'] == 'ping'
        assert results[1]['method'] == 'ping'
        assert results[2]['method'] == 'ping'
