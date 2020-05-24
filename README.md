# aiohttp-rpc

[![NPM](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat-square)](https://www.npmjs.com/package/aiohttp-rpc)  [![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)  [![Build Status](https://img.shields.io/scrutinizer/build/g/expert-m/aiohttp-rpc.svg?style=flat-square)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/build-status/master)  [![GitHub Issues](https://img.shields.io/github/issues/expert-m/aiohttp-rpc.svg?style=flat-square)](https://github.com/expert-m/aiohttp-rpc/issues) [![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)

> Implements JSON-RPC 2.0 using aiohttp

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
from aiohttp import web
import aiohttp_rpc


@aiohttp_rpc.rpc_method()
def proxy(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

async def ping(request):
    return 'pong'


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    aiohttp_rpc.default_rpc_manager.add_methods((
        ('', ping,),
    ))

    app = Application(loop=loop)
    app.router.add_routes((
        web.post('/rpc', aiohttp_rpc.default_rpc_manager.handle_request),
    ))

    run_app(app, host='0.0.0.0', port=8080)
```


### HTTP Client Example
```python3
import aiohttp_rpc
import asyncio

async def run():
    async with aiohttp_rpc.JsonRpcHTTPClient('http://0.0.0.0:8080/rpc') as rpc:
        print(await rpc.proxy(a=4, b=6))
        print(await rpc.call('proxy', a=4, b=6))
        print(await rpc.proxy(1, 2, 3))

loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

[back to top](#table-of-contents)

---

## License
MIT
