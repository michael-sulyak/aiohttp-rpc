import pytest

import aiohttp_rpc


@pytest.mark.asyncio
async def test_default_middleware():
    def method():
        return 'ok'

    rpc_server = aiohttp_rpc.JsonRpcServer()
    rpc_server.add_method(method)


