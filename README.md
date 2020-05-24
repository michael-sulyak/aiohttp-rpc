# aiohttp-rpc

[![PyPI](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat-square)](https://pypi.org/project/aiohttp-rpc/)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7%20%7C%203.8-blue?style=flat-square)](https://docs.python.org/3/whatsnew/3.8.html)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)
[![Build Status](https://img.shields.io/scrutinizer/build/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/build-status/master)
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
def proxy(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    aiohttp_rpc.default_rpc_server.add_methods([
        ('', ping,),
    ])

    app = web.Application()
    app.router.add_routes((
        web.post('/rpc', aiohttp_rpc.default_rpc_server.handle_request),
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
        print(await rpc.proxy(a=4, b=6))
        print(await rpc.call('proxy', a=4, b=6))
        print(await rpc.proxy(1, 2, 3))
        print(await rpc.batch([
            ('proxy', 2,), 
            'proxy2',
            'hi',
        ]))

loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

[back to top](#table-of-contents)

---

## License
MIT
