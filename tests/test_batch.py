import os
import sys

import pytest

import aiohttp_rpc


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tests import utils


@pytest.mark.asyncio
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
        assert await rpc.batch(('method_1', 'method_2',)) == [[1, 2, 1], [1]]
        assert await rpc.batch((('method_1', 4), ('method_1', [], {'a': 5}),)) == [[1, 2, 4], [1, 2, 5]]
