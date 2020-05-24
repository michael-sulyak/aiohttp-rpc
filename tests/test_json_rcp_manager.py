import aiohttp_rpc

import pytest

from aiohttp_rpc import exceptions


@pytest.mark.asyncio
async def test_args():
    def method(a=1):
        return [1, 2, a]

    rpc_manager = aiohttp_rpc.JsonRpcManager()
    rpc_manager.add_method(method)

    assert await rpc_manager.call('method') == [1, 2, 1]
    assert await rpc_manager.call('method', args=[1]) == [1, 2, 1]

    with pytest.raises(exceptions.InvalidParams):
        assert await rpc_manager.call('method', args=[1, 2]) == [1, 2, 1]


@pytest.mark.asyncio
async def test_kwargs():
    def method(a=1, *, b=2):
        return [1, a, b]

    rpc_manager = aiohttp_rpc.JsonRpcManager()
    rpc_manager.add_method(method)

    with pytest.raises(exceptions.InvalidParams):
        assert await rpc_manager.call('method', args=[1, 2]) == [1, 2, 1]

    assert await rpc_manager.call('method', kwargs={'a': 1, 'b': 2}) == [1, 1, 2]
    assert await rpc_manager.call('method', args=[2], kwargs={'b': 2}) == [1, 2, 2]


@pytest.mark.asyncio
async def test_varargs():
    def method(a=1, *args):
        return [a, *args]

    rpc_manager = aiohttp_rpc.JsonRpcManager()
    rpc_manager.add_method(method)

    assert await rpc_manager.call('method') == [1]
    assert await rpc_manager.call('method', args=[2]) == [2]
    assert await rpc_manager.call('method', args=[2, 3]) == [2, 3]


@pytest.mark.asyncio
async def test_varkw():
    def method(a=1, **kwargs):
        return [a, kwargs]

    rpc_manager = aiohttp_rpc.JsonRpcManager()
    rpc_manager.add_method(method)

    with pytest.raises(exceptions.InvalidParams):
        assert await rpc_manager.call('method', args=[1, 2]) == [1, 2, 1]

    assert await rpc_manager.call('method', kwargs={'a': 1, 'b': 2}) == [1, {'b': 2}]

