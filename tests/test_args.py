import functools

import pytest

import aiohttp_rpc
from aiohttp_rpc import errors
from tests import utils


async def test_args(aiohttp_client):
    def method(a=1):
        return [1, 2, a]

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_method(method)

    assert await rpc_server.call('method') == [1, 2, 1]
    assert await rpc_server.call('method', args=[1]) == [1, 2, 1]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == [1, 2, 1]
        assert await rpc.call('method', 1) == [1, 2, 1]


async def test_kwargs(aiohttp_client):
    def method(a=1, *, b=2):
        return [1, a, b]

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_method(method)

    with pytest.raises(errors.InvalidParams):
        await rpc_server.call('method', args=[1, 2])

    assert await rpc_server.call('method', kwargs={'a': 1, 'b': 2}) == [1, 1, 2]
    assert await rpc_server.call('method', args=[2], kwargs={'b': 2}) == [1, 2, 2]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method', a=1, b=2) == [1, 1, 2]

        with pytest.raises(errors.InvalidParams):
            await rpc.call('method', 2, b=2)


async def test_varargs(aiohttp_client):
    def method(a=1, *args):
        return [a, *args]

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_method(method)

    assert await rpc_server.call('method') == [1]
    assert await rpc_server.call('method', args=[2]) == [2]
    assert await rpc_server.call('method', args=[2, 3]) == [2, 3]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == [1]
        assert await rpc.call('method', 2) == [2]
        assert await rpc.call('method', 2, 3) == [2, 3]


async def test_varkw(aiohttp_client):
    def method(a=1, **kwargs):
        return [a, kwargs]

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_method(method)

    with pytest.raises(errors.InvalidParams):
        await rpc_server.call('method', args=[1, 2])

    assert await rpc_server.call('method', kwargs={'a': 1, 'b': 2}) == [1, {'b': 2}]

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        with pytest.raises(errors.InvalidParams):
            await rpc.call('method', 1, 2)

        assert await rpc.call('method', a=1, b=2) == [1, {'b': 2}]


async def test_extra_kwargs(aiohttp_client):
    def method(rpc_request):
        return rpc_request.__class__.__name__

    def method_2(*, rpc_request):
        return rpc_request.__class__.__name__

    rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=(aiohttp_rpc.middlewares.extra_args_middleware,))
    rpc_server.add_method(method)
    rpc_server.add_method(method_2)

    assert await rpc_server.call('method', extra_args={'rpc_request': 123}), 123
    assert await rpc_server.call('method_2', extra_args={'rpc_request': 123}), 123

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == 'JsonRpcRequest'
        assert await rpc.call('method_2') == 'JsonRpcRequest'


async def test_extra_kwargs_with_class(aiohttp_client):
    class TestClass:
        def __init__(self, rpc_request):
            self.rpc_request = rpc_request

        def __str__(self):
            return self.rpc_request.__class__.__name__

    rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=(aiohttp_rpc.middlewares.extra_args_middleware,))
    rpc_server.add_method(aiohttp_rpc.JsonRpcMethod(TestClass, prepare_result=str))

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('TestClass') == 'JsonRpcRequest'


async def test_extra_kwargs_with_wrapper(aiohttp_client):
    def test_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    @test_decorator
    def method(rpc_request):
        return rpc_request.__class__.__name__

    @test_decorator
    def method_2():
        return True

    rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=(aiohttp_rpc.middlewares.extra_args_middleware,))
    rpc_server.add_methods((method, method_2,))

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.call('method') == 'JsonRpcRequest'
        assert await rpc.call('method_2') is True


async def test_builtin_funcs(aiohttp_client):
    rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=(aiohttp_rpc.middlewares.extra_args_middleware,))
    rpc_server.add_method(sum)
    rpc_server.add_method(aiohttp_rpc.JsonRpcMethod(zip, prepare_result=list))

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.sum([1, 2, 3]) == 6
        assert await rpc.zip(['a', 'b'], [1, 2]) == [['a', 1], ['b', 2]]
