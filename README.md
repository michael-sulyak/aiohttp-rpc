# aiohttp-rpc

[![PyPI](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat)](https://pypi.org/project/aiohttp-rpc/)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue?style=flat)](https://www.python.org/downloads/release/python-380/)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)
[![Build Status](https://img.shields.io/scrutinizer/build/g/expert-m/aiohttp-rpc.svg?style=flat)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/build-status/master)
[![Total alerts](https://img.shields.io/lgtm/alerts/g/expert-m/aiohttp-rpc.svg?style=flat)](https://lgtm.com/projects/g/expert-m/aiohttp-rpc/alerts/)
[![GitHub Issues](https://img.shields.io/github/issues/expert-m/aiohttp-rpc.svg?style=flat)](https://github.com/expert-m/aiohttp-rpc/issues)
[![Gitter](https://img.shields.io/gitter/room/aiohttp-rpc/Lobby)](https://gitter.im/aiohttp-rpc/Lobby)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat)](https://opensource.org/licenses/MIT)

> A library for a simple integration of the [JSON-RPC 2.0 protocol](https://www.jsonrpc.org/specification) to a Python application using [aiohttp](https://github.com/aio-libs/aiohttp).
The motivation is to provide a simple, fast and reliable way to integrate the JSON-RPC 2.0 protocol into your application on the server and/or client side.
<br/><br/>
>The library has only one dependency:
>* **[aiohttp](https://github.com/aio-libs/aiohttp)** - Async http client/server framework

## Table Of Contents
- **[Installation](#installation)**
    - **[pip](#pip)**
- **[Usage](#usage)**
  - **[HTTP Server Example](#http-server-example)**
  - **[HTTP Client Example](#http-client-example)**
- [Integration](#Integration)
- [Middleware](#middleware)
- [WebSockets](#websockets)
  - [WS Server Example](#ws-server-example)
  - [WS Client Example](#ws-client-example)
- [API Reference](#api-reference)
- [More examples](#more-examples)
- [License](#license)

## Installation

#### pip
```sh
pip install aiohttp-rpc
```

## Usage

### HTTP Server Example

```python3
from aiohttp import web
import aiohttp_rpc


def echo(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

# If the function has rpc_request in arguments, then it is automatically passed
async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    aiohttp_rpc.rpc_server.add_methods([
        ping,
        echo,
    ])

    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_http_request),
    ])

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
        print(await rpc.notify('echo', 1, 2, 3))
        print(await rpc.get_methods())
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

<p align="center"><b>↑ This is enough to start :sunglasses: ↑</b></p>

---


## Integration

The purpose of this library is to simplify life, and not vice versa.
And so, when you start adding existing functions, some problems may arise.

Existing functions can return objects that are not serialized, but this is easy to fix.
You can write own `json_serialize`:
```python3
import aiohttp_rpc
import typing
import uuid
import json
from dataclasses import dataclass
from functools import partial

@dataclass
class User:  # The object that is not serializable.
    uuid: uuid.UUID
    username: str = 'mike'
    email: str = 'some@mail.com'

async def get_user_by_uuid(user_uuid) -> User:
    # Some function which returns not serializable object.
    # For example, data may be taken from a database.
    return User(uuid=uuid.UUID(user_uuid))


def json_serialize_unknown_value(value):
    if isinstance(value, User):
        return {
            'uuid': str(value.uuid),
            'username': value.username,
            'email': value.email,
        }

    return repr(value)

rpc_server = aiohttp_rpc.JsonRpcServer(
    json_serialize=partial(json.dumps, default=json_serialize_unknown_value),
)
rpc_server.add_method(get_user_by_uuid)
...

"""
Example of response:
{
    "id": null,
    "jsonrpc": "2.0",
    "result": {
        "uuid": "600d57b3-dda8-43d0-af79-3e81dbb344fa",
        "username": "mike",
        "email": "some@mail.com"
    }
}
"""
```

But you can go further.
If you want to use functions that accept custom types,
then you can do something like this:
```python3
# The function (RPC method) that takes a custom type.
def generate_user_token(user: User):
    return f'token-{str(user.uuid).split("-")[0]}'

async def replace_type(data):
    if not isinstance(data, dict) or '__type__' not in data:
        return data

    if data['__type__'] == 'user':
        return await get_user_by_uuid(data['uuid'])

    raise aiohttp_rpc.errors.InvalidParams

# The middleware that converts types
async def type_conversion_middleware(request, handler):
    for i, arg in enumerate(request.args):
        request.args[i] = await replace_type(arg)

    for key, value in request.kwargs.items():
        request.kwargs[key] = await replace_type(value)

    return await handler(request)


rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=[
    aiohttp_rpc.middlewares.exception_middleware,
    aiohttp_rpc.middlewares.extra_args_middleware,
    type_conversion_middleware,
])

"""
Request:
{
    "id": 1234,
    "jsonrpc": "2.0",
    "method": "generate_user_token",
    "params": [{"__type__": "user", "uuid": "600d57b3-dda8-43d0-af79-3e81dbb344fa"}]
}

Response:
{
    "id": 1234,
    "jsonrpc": "2.0",
    "result": "token-600d57b3"
}
"""
```

[Middleware](#middleware) allows you to replace arguments, responses, and more.

If you want to add permission checking for each method,
then you can override the class `JsonRpcMethod` or use [middleware](#middleware).

[back to top](#table-of-contents)

---


## Middleware

Middleware is used for [RPC Request / RPC Response](#protocol) processing.
It has a similar interface as [aiohttp middleware](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares).

```python3
import aiohttp_rpc
import typing

async def simple_middleware(request: aiohttp_rpc.JsonRpcRequest, handler: typing.Callable) -> aiohttp_rpc.JsonRpcResponse:
    # Code to be executed for each RPC request before
    # the method (and later middleware) are called.

    response = await handler(request)

    # Code to be executed for each RPC request / RPC response after
    # the method is called.

    return response

rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=[
     aiohttp_rpc.middlewares.exception_middleware,
     simple_middleware,
])
```

Or use [aiohttp middlewares](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares) to process `web.Request`/`web.Response`.

[back to top](#table-of-contents)

---


## WebSockets

### WS Server Example

```python3
from aiohttp import web
import aiohttp_rpc


async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    rpc_server = aiohttp_rpc.WsJsonRpcServer(
        middlewares=aiohttp_rpc.middlewares.DEFAULT_MIDDLEWARES,
    )
    rpc_server.add_method(ping)

    app = web.Application()
    app.router.add_routes([
        web.get('/rpc', rpc_server.handle_http_request),
    ])
    app.on_shutdown.append(rpc_server.on_shutdown)
    web.run_app(app, host='0.0.0.0', port=8080)
```

### WS Client Example
```python3
import aiohttp_rpc
import asyncio

async def run():
    async with aiohttp_rpc.WsJsonRpcClient('http://0.0.0.0:8080/rpc') as rpc:
        print(await rpc.ping())
        print(await rpc.notify('ping'))
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

## API Reference


### `server`
  * `class JsonRpcServer(BaseJsonRpcServer)`
    * `def __init__(self, *, json_serialize=json_serialize, middlewares=(), methods=None)`
    * `def add_method(self, method, *, replace=False) -> JsonRpcMethod`
    * `def add_methods(self, methods, replace=False) -> typing.List[JsonRpcMethod]`
    * `def get_methods(self) -> dict`
    * `async def handle_http_request(self, http_request: web.Request) -> web.Response`
 
  * `class WsJsonRpcServer(BaseJsonRpcServer)`
  * `rpc_server: JsonRpcServer`
  

### `client`
  * `class JsonRpcClient(BaseJsonRpcClient)`
    * `async def connect(self)`
    * `async def disconnect(self)`
    * `async def call(self, method: str, *args, **kwargs)`
    * `async def notify(self, method: str, *args, **kwargs)`
    * `async def batch(self, methods: typing.Iterable[typing.Union[str, list, tuple]])`
    * `async def batch_notify(self, methods: typing.Iterable[typing.Union[str, list, tuple]])`
  
  * `class WsJsonRpcClient(BaseJsonRpcClient)`
  * `class UnlinkedResults`

### `protocol`
  * `class JsonRpcRequest`
    * `method: str`
    * `msg_id: typing.Any`
    * `jsonrpc: str`
    * `extra_args: dict`
    * `context: dict`
    * `params: typing.Any`
    * `args: typing.Optional[typing.Union[list, tuple]]`
    * `kwargs: typing.Optional[dict]`
    * `is_notification: bool`
    
  * `class JsonRpcResponse`
    * `jsonrpc: str`
    * `msg_id: typing.Any`
    * `result: typing.Any`
    * `error: typing.Optional[JsonRpcError]`
    * `context: dict`
    
  * `class JsonRpcMethod(BaseJsonRpcMethod)`
    * `def __init__(self, prefix, func, *, custom_name=None, add_extra_args=True, prepare_result=None)`

### `decorators`
  * `def rpc_method(prefix='', *, rpc_server=default_rpc_server, custom_name=None, add_extra_args=True)`

### `errors`
  * `class JsonRpcError(RuntimeError)`
  * `class ServerError(JsonRpcError)`
  * `class ParseError(JsonRpcError)`
  * `class InvalidRequest(JsonRpcError)`
  * `class MethodNotFound(JsonRpcError)`
  * `class InvalidParams(JsonRpcError)`
  * `class InternalError(JsonRpcError)`
  * `DEFAULT_KNOWN_ERRORS`
  
### `middlewares`
  * `async def extra_args_middleware(request, handler)`
  * `async def exception_middleware(request, handler)`
  * `DEFAULT_MIDDLEWARES`

### `utils`
  * `def json_serialize(*args, **kwargs)`

### `constants`
  * `NOTHING`
  * `VERSION_2_0`

[back to top](#table-of-contents)

---


## More examples

**The library allows you to add methods in many ways:**
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

**Example with built-in functions:**
```python3
# Server
import aiohttp_rpc

rpc_server = aiohttp_rpc.JsonRpcServer(middlewares=[aiohttp_rpc.middlewares.extra_args_middleware])
rpc_server.add_method(sum)
rpc_server.add_method(aiohttp_rpc.JsonRpcMethod('', zip, prepare_result=list))
...

# Client
async with aiohttp_rpc.JsonRpcClient('/rpc') as rpc:
    assert await rpc.sum([1, 2, 3]) == 6
    assert await rpc.zip(['a', 'b'], [1, 2]) == [['a', 1], ['b', 2]]
```

**Example with the decorator:**
```python3
@aiohttp_rpc.rpc_method()
def echo(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_http_request),
    ])
    web.run_app(app, host='0.0.0.0', port=8080)
```

[back to top](#table-of-contents)

---


## License
MIT
