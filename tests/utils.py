import aiohttp
from aiohttp import web

import aiohttp_rpc


async def make_client(aiohttp_client, rpc_server: aiohttp_rpc.JsonRpcServer) -> aiohttp.ClientSession:
    app = web.Application()
    app.router.add_post('/rpc', rpc_server.handle_http_request)
    return await aiohttp_client(app)


async def make_ws_client(aiohttp_client, rpc_server: aiohttp_rpc.WsJsonRpcServer) -> aiohttp.ClientSession:
    app = web.Application()
    app.router.add_get('/rpc', rpc_server.handle_http_request)
    app.on_shutdown.append(rpc_server.on_shutdown)
    return await aiohttp_client(app)
