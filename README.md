# aiohttp-rpc

[![PyPI](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat-square)](https://pypi.org/project/aiohttp-rpc/)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue?style=flat-square)](https://docs.python.org/3/whatsnew/3.8.html)
[![AIOHTTP Version](https://img.shields.io/badge/aiohttp-3-blue?style=flat-square)](https://docs.aiohttp.org/en/stable/)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)
[![Build Status](https://img.shields.io/scrutinizer/build/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/build-status/master)
[![Total alerts](https://img.shields.io/lgtm/alerts/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://lgtm.com/projects/g/expert-m/aiohttp-rpc/alerts/)
[![GitHub Issues](https://img.shields.io/github/issues/expert-m/aiohttp-rpc.svg?style=flat-square)](https://github.com/expert-m/aiohttp-rpc/issues)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)

> A library for a simple integration of the JSON-RPC 2.0 protocol to a Python application using [aiohttp](https://github.com/aio-libs/aiohttp).
The motivation is to provide a simple, fast and reliable way to integrate the JSON-RPC 2.0 protocol into your application on the server and/or client side.
<br/><br/>
>The library has only one dependency:
>* **[aiohttp](https://github.com/aio-libs/aiohttp)** - Async http client/server framework

## Table Of Contents
- [Installation](#installation)
    - [pip](#pip)
- [API Reference](#api-reference)
  - [HTTP Server Example](#http-server-example)
  - [HTTP Client Example](#http-client-example)
  - [Middleware](#middleware)
  - [More examples](#more-examples)
- [License](#license)

## Installation

#### pip
```bash
pip install aiohttp-rpc
```

# Usage

### HTTP Server Example

```python3
import asyncio
from aiohttp import web
import aiohttp_rpc


@aiohttp_rpc.rpc_method()
def echo(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    aiohttp_rpc.rpc_server.add_methods([
        ('', ping,),
    ])

    app = web.Application()
    app.router.add_routes((
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_request),
    ))

    web.run_app(app, host='0.0.0.0', port=8080)
```

### HTTP Client Example
```python3
import aiohttp_rpc
import asyncio

async def run():
    async with aiohttp_rpc.JsonRpcClient('http://0.0.0.0:8080/rpc') as rpc:
        print(await rpc.ping())
        print(await rpc.echo(a=4, b=6))
        print(await rpc.call('echo', a=4, b=6))
        print(await rpc.echo(1, 2, 3))
        print(await rpc.batch([
            ['echo', 2], 
            'echo2',
            'ping',
        ]))

loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

[back to top](#table-of-contents)

---


### Middleware

Middleware is used for request/response processing. 

```python3
import aiohttp_rpc

class TokenMiddleware(aiohttp_rpc.BaseJsonRpcMiddleware):
    async def __call__(self, request: aiohttp_rpc.JsonRpcRequest) -> aiohttp_rpc.JsonRpcResponse:
        if request.http_request and request.http_request.headers.get('X-App-Token') != 'qwerty':
            return protocol.JsonRpcResponse(error=exceptions.InvalidRequest('Invalid token'))

        return await self.get_response(request)

rpc_server = aiohttp_rpc.JsonRpcServer(middleware=[
     TokenMiddleware,
     aiohttp_rpc.ExceptionMiddleware,
])
```

[back to top](#table-of-contents)

---

### More examples

**Adding methods:**
```python3
import aiohttp_rpc

async def ping(rpc_request): return 'pong'
async def ping_1(rpc_request): return 'pong 1'
async def ping_2(rpc_request): return 'pong 2'
async def ping_3(rpc_request): return 'pong 3'

rpc_server = aiohttp_rpc.JsonRpcServer()
rpc_server.add_method(ping)  # 'ping'
rpc_server.add_method(['', ping_1])  # 'ping_1'
rpc_server.add_method(['super', ping_1])  # 'super__ping_1'
rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('super', ping_2))  # 'super__ping_2'
rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('', ping_2, custom_name='super_ping'))  # 'super__super_ping'

# Replace method
rpc_server.add_method(['', ping_1], replace=True)  # 'ping_1'


rpc_server.add_methods([ping_1, ping_2], replace=True)  # 'ping_1', 'ping_2'
rpc_server.add_methods([['new', ping_2], ping_3])  # 'new__ping2', 'ping_3'
```

[back to top](#table-of-contents)

---


## License
MIT
