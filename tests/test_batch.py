import pytest

import aiohttp_rpc
from tests import utils


async def test_batch(aiohttp_client):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_methods((
        method_1,
        method_2,
    ))

    assert await rpc_server.call('method_1') == [1, 2, 1]
    assert await rpc_server.call('method_2') == [1]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
        ) == ([1, 2, 1], [1],)
        assert await rpc.batch(
            rpc.methods.method_1.request(4),
            rpc.methods.method_1.request(a=5),
        ) == ([1, 2, 4], [1, 2, 5],)


async def test_batch_with_some_notifications(aiohttp_client):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_methods((
        method_1,
        method_2,
    ))

    assert await rpc_server.call('method_1') == [1, 2, 1]
    assert await rpc_server.call('method_2') == [1]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.notification(),
        ) == ([1, 2, 1], None,)
        assert await rpc.batch(
            rpc.methods.method_1.request(4),
            rpc.methods.method_1.notification(a=5),
        ) == ([1, 2, 4], None,)


async def test_unlinked_results(aiohttp_client, mocker):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_methods((
        method_1,
        method_2,
    ))

    client = await utils.make_client(aiohttp_client, rpc_server)

    async def test_send_json_1(data, **kwargs):
        data = [
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
            {'id': data[0]['id'], 'jsonrpc': '2.0', 'result': [1, 2, 1]},
        ]
        return data, {}

    async def test_send_json_2(data, **kwargs):
        data = [
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
            {'id': data[0]['id'], 'jsonrpc': '2.0', 'result': [1, 2, 1]},
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
        ]
        return data, {}

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_1)
        unlinked_results = aiohttp_rpc.JSONRPCUnlinkedResults(results=[[1]])
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
        ) == ([1, 2, 1], unlinked_results,)

        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_2)
        unlinked_results = aiohttp_rpc.JSONRPCUnlinkedResults(results=[[1], [1]])
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
            rpc.methods.method_3.request(),
        ) == (
                   [1, 2, 1],
                   unlinked_results,
                   unlinked_results,
               )


async def test_duplicated_results(aiohttp_client, mocker):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_methods((
        method_1,
        method_2,
    ))

    client = await utils.make_client(aiohttp_client, rpc_server)

    async def test_send_json_1(data, **kwargs):
        data = [
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
            {'id': data[0]['id'], 'jsonrpc': '2.0', 'result': [1, 2, 1]},
        ]
        return data, {}

    async def test_send_json_2(data, **kwargs):
        data = [
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
            {'id': data[0]['id'], 'jsonrpc': '2.0', 'result': [1, 2, 1]},
            {'id': data[0]['id'], 'jsonrpc': '2.0', 'result': [1, 2, 3]},
            {'id': None, 'jsonrpc': '2.0', 'result': [1]},
        ]
        return data, {}

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_1)
        unlinked_results = aiohttp_rpc.JSONRPCUnlinkedResults(results=[[1]])
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
        ) == ([1, 2, 1], unlinked_results,)

        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_2)
        unlinked_results = aiohttp_rpc.JSONRPCUnlinkedResults(results=[[1], [1]])
        duplicated_results = aiohttp_rpc.JSONRPCDuplicatedResults(results=[[1, 2, 1], [1, 2, 3]])
        assert await rpc.batch(
            rpc.methods.method_1.request(),
            rpc.methods.method_2.request(),
            rpc.methods.method_3.request(),
        ) == (
                   duplicated_results,
                   unlinked_results,
                   unlinked_results,
               )


async def test_http_max_batch(aiohttp_client):
    server = aiohttp_rpc.JSONRPCServer(max_batch=2)

    def ok(): return True

    server.add_method(ok)
    client = await utils.make_client(aiohttp_client, server)
    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        result, _ = await rpc.send_json([
            {'jsonrpc': '2.0', 'method': 'ok', 'id': 1},
            {'jsonrpc': '2.0', 'method': 'ok', 'id': 2},
            {'jsonrpc': '2.0', 'method': 'ok', 'id': 3},
        ])
        assert result == {
            'jsonrpc': '2.0',
            'error': {
                'code': -32600,
                'message': 'Invalid Request',
                'data': {'details': 'Batch too large.'},
            },
            'id': None,
        }


async def test_http_max_payload(aiohttp_client):
    server = aiohttp_rpc.JSONRPCServer()
    client = await utils.make_client(aiohttp_client, server, client_max_size=10)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        with pytest.raises(aiohttp_rpc.errors.HTTPStatusError):
            await rpc.send_json({'jsonrpc': '2.0', 'method': 'x', 'id': 1, 'params': 'xxxxxxxxxxxxx'})
