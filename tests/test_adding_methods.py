import pytest

import aiohttp_rpc


@pytest.mark.asyncio
async def test_adding_method():
    def method():
        pass

    rpc_server = aiohttp_rpc.JsonRpcServer()

    rpc_server.add_method(method)
    assert rpc_server.methods['method'].func == method

    rpc_server.add_method(['test', method])
    assert rpc_server.methods['test__method'].func == method

    rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('test_2', method))
    assert rpc_server.methods['test_2__method'].func == method

    rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('', method, custom_name='test'))
    assert rpc_server.methods['test'].func == method

    rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('test', method, custom_name='test'))
    assert rpc_server.methods['test__test'].func == method


@pytest.mark.asyncio
async def test_adding_methods():
    def method_1():
        pass

    def method_2():
        pass

    rpc_server = aiohttp_rpc.JsonRpcServer()

    rpc_server.add_methods([method_1, method_2])
    assert rpc_server.methods['method_1'].func == method_1
    assert rpc_server.methods['method_2'].func == method_2
