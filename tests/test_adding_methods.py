import aiohttp_rpc


async def test_adding_method():
    def method():
        pass

    class TestClass:
        def method_1(self):
            pass

        @classmethod
        def method_2(cls):
            pass

        @staticmethod
        def method_3():
            pass

    rpc_server = aiohttp_rpc.JSONRPCServer()

    rpc_server.add_method(method)
    assert rpc_server.methods['method'].func == method

    rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(method, name='test'))
    assert rpc_server.methods['test'].func == method

    test_class = TestClass()
    rpc_server.add_method(test_class.method_1)
    assert rpc_server.methods['method_1'].func == test_class.method_1

    rpc_server.add_method(TestClass.method_2)
    assert rpc_server.methods['method_2'].func == TestClass.method_2

    rpc_server.add_method(TestClass.method_3)
    assert rpc_server.methods['method_3'].func == TestClass.method_3


async def test_adding_methods():
    def method_1():
        pass

    def method_2():
        pass

    rpc_server = aiohttp_rpc.JSONRPCServer()

    rpc_server.add_methods([method_1, method_2])
    assert rpc_server.methods['method_1'].func == method_1
    assert rpc_server.methods['method_2'].func == method_2
