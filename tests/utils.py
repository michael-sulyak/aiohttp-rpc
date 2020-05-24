import aiohttp
from aiohttp import web

import aiohttp_rpc


async def make_client(aiohttp_client, rpc_server: aiohttp_rpc.JsonRpcServer) -> aiohttp.ClientSession:
    app = web.Application()
    app.router.add_post('/rpc', rpc_server.handle_request)
    return await aiohttp_client(app)
