import aiohttp_rpc
from tests import utils


async def test_batch(aiohttp_client):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_methods((
        method_1,
        method_2,
    ))

    assert await rpc_server.call('method_1') == [1, 2, 1]
    assert await rpc_server.call('method_2') == [1]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.batch(('method_1', 'method_2',)) == ([1, 2, 1], [1],)
        assert await rpc.batch((('method_1', 4), ('method_1', [], {'a': 5}),)) == ([1, 2, 4], [1, 2, 5],)


async def test_unlinked_results(aiohttp_client, mocker):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JsonRpcServer()
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

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_1)
        unlinked_results = aiohttp_rpc.JsonRpcUnlinkedResults(results=[[1]])
        assert await rpc.batch(('method_1', 'method_2',)) == ([1, 2, 1], unlinked_results,)

        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_2)
        unlinked_results = aiohttp_rpc.JsonRpcUnlinkedResults(results=[[1], [1]])
        assert await rpc.batch(('method_1', 'method_2', 'method_2',)) == (
            [1, 2, 1],
            unlinked_results,
            unlinked_results,
        )


async def test_duplicated_results(aiohttp_client, mocker):
    def method_1(a=1):
        return [1, 2, a]

    def method_2():
        return [1]

    rpc_server = aiohttp_rpc.JsonRpcServer()
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

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_1)
        unlinked_results = aiohttp_rpc.JsonRpcUnlinkedResults(results=[[1]])
        assert await rpc.batch(('method_1', 'method_2',)) == ([1, 2, 1], unlinked_results,)

        mocker.patch.object(rpc, 'send_json', new_callable=lambda: test_send_json_2)
        unlinked_results = aiohttp_rpc.JsonRpcUnlinkedResults(results=[[1], [1]])
        duplicated_results = aiohttp_rpc.JsonRpcDuplicatedResults(results=[[1, 2, 1], [1, 2, 3]])
        assert await rpc.batch(('method_1', 'method_2', 'method_2',)) == (
            duplicated_results,
            unlinked_results,
            unlinked_results,
        )
