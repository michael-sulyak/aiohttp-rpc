import asyncio
import datetime

from aiohttp import web_ws

import aiohttp_rpc
from tests import utils


async def test_args(aiohttp_client):
    def method(a=1):
        return [1, 2, a]

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(method)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == [1, 2, 1]
        assert await rpc.call('method', 1) == [1, 2, 1]


async def test_batch(aiohttp_client):
    def method_1(a=1):
        return [1, a]

    def method_2():
        return 1

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_methods((method_1, method_2,))

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
        ) == ([1, 1], 1,)
        assert await rpc.batch(
            rpc.methods.method_1.request(4),
            rpc.methods.method_1.request(a=5),
        ) == ([1, 4], [1, 5],)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.batch_notify(
            rpc.methods.method_1.notification(),
            rpc.methods.method_2.notification(),
        ) is None
        assert await rpc.batch_notify(
            rpc.methods.method_1.request(4),
            rpc.methods.method_1.request(a=5),
        ) is None


async def test_several_requests(aiohttp_client):
    async def method(a):
        await asyncio.sleep(0.2)
        return a

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(method)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        started_at = datetime.datetime.now()

        result = await asyncio.gather(*(
            rpc.call('method', i)
            for i in range(10)
        ))

        finished_at = datetime.datetime.now()

        assert finished_at - started_at < datetime.timedelta(seconds=1)
        assert result == list(range(10))


async def test_inject_ws_client_middleware(aiohttp_client, mocker):
    async def method(*, ws_rpc_client: aiohttp_rpc.WSJSONRPCClient, **kwargs):
        await ws_rpc_client.notify('ping')
        await ws_rpc_client.notify('ping')
        await ws_rpc_client.notify('ping')

    rpc_server = aiohttp_rpc.WSJSONRPCServer(
        middlewares=[
            *aiohttp_rpc.middlewares.DEFAULT_MIDDLEWARES,
            aiohttp_rpc.middlewares.inject_ws_client_middleware,
        ],
    )
    rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(method, pass_extra_kwargs=True))

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    future = asyncio.Future()

    results = []

    def json_request_handler(*, ws_connect, ws_msg, json_requests):
        results.extend(json_requests)

        if len(results) == 3:
            future.set_result(results)

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
        json_requests_handler=json_request_handler,
    ) as rpc:
        json_request_handler = mocker.patch.object(
            rpc,
            '_json_requests_handler',
            side_effect=rpc._json_requests_handler,
        )
        await rpc.methods.method()

        await asyncio.wait_for(future, timeout=3)
        assert json_request_handler.call_count == 3
        assert results[0]['method'] == 'ping'
        assert results[1]['method'] == 'ping'
        assert results[2]['method'] == 'ping'


async def test_ws_response_kwargs(aiohttp_client):
    rpc_server = aiohttp_rpc.WSJSONRPCServer(
        ws_response_kwargs=dict(
            timeout=10.0,
            max_msg_size=2048,
        ),
    )

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
    ):
        rpc_websocket: web_ws.WebSocketResponse
        for rpc_websocket in rpc_server.rpc_websockets:
            assert rpc_websocket._timeout == 10.0
            assert rpc_websocket._max_msg_size == 2048


async def test_ws_response_cls(aiohttp_client):
    rpc_server = aiohttp_rpc.WSJSONRPCServer(
        ws_response_kwargs={'max_msg_size': 2048},
    )

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
    ):
        for rpc_websocket in rpc_server.rpc_websockets:
            assert rpc_websocket._timeout == 10
            assert rpc_websocket._max_msg_size == 2048
