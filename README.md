# aiohttp-rpc

[![PyPI](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat)](https://pypi.org/project/aiohttp-rpc/)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?style=flat)](https://www.python.org/downloads/release/python-3136/)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)
[![GitHub Issues](https://img.shields.io/github/issues/expert-m/aiohttp-rpc.svg?style=flat)](https://github.com/expert-m/aiohttp-rpc/issues)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat)](https://opensource.org/licenses/MIT)

> A library for simple integration of the [JSON-RPC 2.0 protocol](https://www.jsonrpc.org/specification) into a Python application using [aiohttp](https://github.com/aio-libs/aiohttp).  
The motivation is to provide a simple, fast, and reliable way to integrate the JSON-RPC 2.0 protocol into your application on the server and/or client side.

>The library has only one dependency:
>* **[aiohttp](https://github.com/aio-libs/aiohttp)** — Async HTTP client/server framework

## Table Of Contents
- **[Installation](#installation)**
    - **[pip](#pip)**
- **[Usage](#usage)**
  - **[HTTP Server Example](#http-server-example)**
  - **[HTTP Client Example](#http-client-example)**
- [Integration](#integration)
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

```python
from aiohttp import web
import aiohttp_rpc


def echo(*args, **kwargs):
    return {
        'args': args,
        'kwargs': kwargs,
    }

# If the function has `rpc_request` in its signature, it is automatically passed
# by the default middleware set (DEFAULT_MIDDLEWARES).
async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    aiohttp_rpc.rpc_server.add_methods([
        ping,
        echo,
    ])

    # `add_introspection` is optional.
    # It adds methods `get_methods` and `get_method` that provide info about available methods.
    aiohttp_rpc.rpc_server.add_introspection()

    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_http_request),
    ])
    web.run_app(app, host='0.0.0.0', port=8080)
```

### HTTP Client Example

```python
import aiohttp_rpc
import asyncio


async def run():
    async with aiohttp_rpc.JSONRPCClient('http://0.0.0.0:8080/rpc') as rpc:
        # Usual way of calling methods:
        print('#1', await rpc.methods.ping())  # Call without arguments.
        print('#2', await rpc.methods.echo('one', 'two'))  # Call with args.
        print('#3', await rpc.methods.echo(three='3'))  # Call with kwargs (you can use only args or only kwargs).
        
        # Other ways of calling methods:
        print('#4', await rpc.call('echo', three='3'))
        print('#5', await rpc.notify('echo', 123))
        print('#7', await rpc.direct_call(aiohttp_rpc.JSONRPCRequest(id=123, method_name='ping')))
        
        # Batch calling:
        print('#8', await rpc.batch(
            rpc.methods.ping.request(),
            rpc.methods.echo.request('one', 'two'),
            rpc.methods.echo.request(three='3'),
        ))
        print('#9', await rpc.batch_notify(
            rpc.methods.ping.notification(),
            rpc.methods.echo.notification('one', 'two'),
            rpc.methods.echo.notification(three='3'),
        ))
        
        # Get all available methods on the server:
        print('#10', await rpc.methods.get_methods())


loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

This prints:
```text
#1 pong
#2 {'args': ['one', 'two'], 'kwargs': {}}
#3 {'args': [], 'kwargs': {'three': '3'}}
#4 {'args': [], 'kwargs': {'three': '3'}}
#5 None
#7 JSONRPCResponse(id=123, jsonrpc='2.0', result='pong', error=None, context={'http_response': ...})
#8 ('pong', {'args': ['one', 'two'], 'kwargs': {}}, {'args': [], 'kwargs': {'three': '3'}})
#9 None
#10 {'ping': {'doc': None, 'args': ['rpc_request'], 'kwargs': []}, 'echo': {'doc': None, 'args': [], 'kwargs': []}, 'get_method': {'doc': None, 'args': ['name'], 'kwargs': []}, 'get_methods': {'doc': None, 'args': [], 'kwargs': []}}
```

[back to top](#table-of-contents)

---

<p align="center"><b>↑ This is enough to start :sunglasses: ↑</b></p>

---


## Integration

The purpose of this library is to simplify your life, not complicate it.  
When you start adding existing functions, some issues may arise.

Existing functions can return objects that are not JSON-serializable — but this is easy to fix.
You can provide your own `json_serialize`:

```python
from aiohttp import web
import aiohttp_rpc
import uuid
import json
from dataclasses import dataclass
from functools import partial


@dataclass
class User:  # An object that is not JSON-serializable by default.
    uuid: uuid.UUID
    username: str = 'mike'
    email: str = 'some@mail.com'


async def get_user_by_uuid(user_uuid) -> User:
    # Some function which returns a non-serializable object.
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


if __name__ == '__main__':
    rpc_server = aiohttp_rpc.JSONRPCServer(
        json_serialize=partial(json.dumps, default=json_serialize_unknown_value),
    )
    rpc_server.add_method(get_user_by_uuid)

    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', rpc_server.handle_http_request),
    ])
    web.run_app(app, host='0.0.0.0', port=8080)
...

"""
Example of response:
{
    "id": 1,
    "jsonrpc": "2.0",
    "result": {
        "uuid": "600d57b3-dda8-43d0-af79-3e81dbb344fa",
        "username": "mike",
        "email": "some@mail.com"
    }
}
"""
```

You can go further.  
If you want to use functions that accept custom types, you can do something like this:

```python
# The function (RPC method) that takes a custom type.
def generate_user_token(user: User):
    return f'token-{str(user.uuid).split("-")[0]}'


async def replace_type(data):
    if not isinstance(data, dict) or '__type__' not in data:
        return data

    if data['__type__'] == 'user':
        return await get_user_by_uuid(data['uuid'])

    raise aiohttp_rpc.errors.InvalidParams


# A middleware that converts types.
async def type_conversion_middleware(request, handler):
    request.set_args_and_kwargs(
        args=[await replace_type(arg) for arg in request.args],
        kwargs={key: await replace_type(value) for key, value in request.kwargs.items()},
    )
    return await handler(request)


rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[
    aiohttp_rpc.middlewares.exception_middleware,
    aiohttp_rpc.middlewares.inject_request_middleware,
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

If you want to add permission checks for each method, then you can override the class `JSONRPCMethod` or use [middleware](#middleware).

[back to top](#table-of-contents)

---


## Middleware

Middleware is used for [RPC Request / RPC Response](#api-reference) processing.
It has an interface similar to [aiohttp middleware](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares).

```python
import aiohttp_rpc
import typing


async def simple_middleware(request: aiohttp_rpc.JSONRPCRequest,
                            handler: typing.Callable) -> aiohttp_rpc.JSONRPCResponse:
    # Code executed for each RPC request before
    # the method (and later middleware) are called.

    response = await handler(request)

    # Code executed for each RPC request / RPC response after
    # the method is called.

    return response


rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[
    aiohttp_rpc.middlewares.exception_middleware,
    simple_middleware,
])
```

Or use [aiohttp middlewares](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares) to process `web.Request`/`web.Response`.

[back to top](#table-of-contents)

---


## WebSockets

### WS Server Example

```python
from aiohttp import web
import aiohttp_rpc


def echo(*args, **kwargs):
    return {'args': args, 'kwargs': kwargs}


async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    rpc_server = aiohttp_rpc.WSJSONRPCServer(
        middlewares=aiohttp_rpc.middlewares.DEFAULT_MIDDLEWARES,
    )
    rpc_server.add_methods([ping, echo])

    app = web.Application()
    app.router.add_routes([
        web.get('/rpc', rpc_server.handle_http_request),
    ])
    app.on_shutdown.append(rpc_server.on_shutdown)
    web.run_app(app, host='0.0.0.0', port=8080)
```

### WS Client Example

```python
import aiohttp_rpc
import asyncio


async def run():
    async with aiohttp_rpc.WSJSONRPCClient('http://0.0.0.0:8080/rpc') as rpc:
        print(await rpc.methods.ping())  # Send a request and wait for the response.
        print(await rpc.methods.echo('request'))  # Call with positional args.
        await rpc.methods.echo.notify('notification')  # Send notification (no response is expected).
        print(rpc.methods.echo.request('some request'))  # Generate a request object that can be used in a batch.
        print(rpc.methods.echo.notification('some notification'))  # Generate a notification object (no `id`).
        print(await rpc.notify('ping'))  # None
        print(await rpc.batch(
            rpc.methods.echo.request('test'),
            rpc.methods.echo.notification(a=1, b=2),
            rpc.methods.ping.request(),
        ))


loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

[back to top](#table-of-contents)

---

## API Reference


### `server`
  * `class JSONRPCServer(BaseJSONRPCServer)`
    * `def __init__(self, *, json_serialize=json_serialize, middlewares=(), methods=None, max_batch=None, max_payload_bytes=1_048_576)`
    * `def add_method(self, method, *, replace=False) -> JSONRPCMethod`
    * `def add_methods(self, methods, replace=False) -> Tuple[JSONRPCMethod, ...]`
    * `def add_introspection(self) -> None`
    * `def get_method(self, name) -> Optional[Mapping]`
    * `def get_methods(self) -> Mapping[str, Mapping]`
    * `async def handle_http_request(self, http_request: web.Request) -> web.Response`
 
  * `class WSJSONRPCServer(BaseJSONRPCServer)`
    * `async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse`
    * `async def on_shutdown(self, app: web.Application) -> None`
  * `rpc_server: JSONRPCServer` (pre-configured with `DEFAULT_MIDDLEWARES`)
  

### `client`
  * `class JSONRPCClient(BaseJSONRPCClient)`
    * `async def connect(self) -> None`
    * `async def disconnect(self) -> None`
    * `async def call(self, method: str, *args, **kwargs)`
    * `async def notify(self, method: str, *args, **kwargs) -> None`
    * `async def batch(self, *requests, save_order: bool = True) -> Sequence`
    * `async def batch_notify(self, *requests) -> None`
    * `async def direct_call(self, request: JSONRPCRequest, **request_kwargs) -> Optional[JSONRPCResponse]`
    * `async def direct_batch(self, batch_request: JSONRPCBatchRequest, **request_kwargs) -> Optional[JSONRPCBatchResponse]`
    * `methods: JSONRPCClientMethods` (attribute for ergonomic, dynamic method access)
  
  * `class WSJSONRPCClient(BaseJSONRPCClient)` — same high-level API as the HTTP client, over WebSockets.

### `protocol`
  * `class JSONRPCRequest`
    * `id: Union[int, str, None]`
    * `method_name: str`
    * `jsonrpc: str`
    * `extra_args: MutableMapping`
    * `context: MutableMapping`
    * `params: Any`
    * `args: Optional[Sequence]`
    * `kwargs: Optional[Mapping]`
    * `is_notification: bool`
    
  * `class JSONRPCResponse`
    * `id: Union[int, str, None]`
    * `jsonrpc: str`
    * `result: Any`
    * `error: Optional[JSONRPCError]`
    * `context: MutableMapping`
    
  * `class JSONRPCMethod(BaseJSONRPCMethod)`
    * `def __init__(self, func, *, name=None, add_extra_args=True, prepare_result=None)`
  
  * `class JSONRPCUnlinkedResults`

  * `class JSONRPCDuplicatedResults`

### `decorators`
  * `def rpc_method(name: Optional[str] = None, *, rpc_server=default_rpc_server, add_extra_args=True, prepare_result=None)`

### `errors`
  * `class JSONRPCError(RuntimeError)`
  * `class ServerError(JSONRPCError)`
  * `class ParseError(JSONRPCError)`
  * `class InvalidRequest(JSONRPCError)`
  * `class MethodNotFound(JSONRPCError)`
  * `class InvalidParams(JSONRPCError)`
  * `class InternalError(JSONRPCError)`
  * `class EmptyResponse(JSONRPCError)`
  * `class RequestTimeoutError(JSONRPCError)`
  * `DEFAULT_KNOWN_ERRORS`
  
### `middlewares`
  * `async def inject_request_middleware(request, handler)` — injects `rpc_request` into method arguments.
  * `async def exception_middleware(request, handler)` — converts exceptions into JSON-RPC errors.
  * `async def logging_middleware(request, handler)` — logs raw requests and responses.
  * `async def ws_client_for_server_response(request, handler)` — attaches a WS client into context for server-initiated responses.
  * `DEFAULT_MIDDLEWARES = (exception_middleware, inject_request_middleware)`

### `utils`
  * `def json_serialize(value) -> str`
  * `def convert_params_to_args_and_kwargs(params) -> Tuple[Sequence, Mapping]`
  * `def parse_args_and_kwargs(args, kwargs) -> Tuple[Any, Sequence, Mapping]`
  * `def get_random_id() -> str`
  * `def get_exc_message(exc: BaseException) -> str`
  * `def collect_batch_result(batch_request, batch_response) -> Tuple[Any, ...]`

### `constants`
  * `NOTHING`
  * `VERSION_2_0`

[back to top](#table-of-contents)

---


## More examples

**The library allows you to add methods in many ways:**

```python
import aiohttp_rpc

def ping_1(rpc_request): return 'pong 1'
def ping_2(rpc_request): return 'pong 2'
def ping_3(rpc_request): return 'pong 3'

rpc_server = aiohttp_rpc.JSONRPCServer()
rpc_server.add_method(ping_1)  # 'ping_1'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_2))  # 'ping_2'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_3, name='third_ping'))  # 'third_ping'
rpc_server.add_methods([ping_3])  # 'ping_3'

# Replace method
rpc_server.add_method(ping_1, replace=True)  # 'ping_1'
rpc_server.add_methods([ping_1, ping_2], replace=True)  # 'ping_1', 'ping_2'
```

**Example with built-in functions:**

```python
# Server
import aiohttp_rpc


rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[aiohttp_rpc.middlewares.inject_request_middleware])
rpc_server.add_method(sum)
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(zip, prepare_result=list))
...

# Client
async with aiohttp_rpc.JSONRPCClient('/rpc') as rpc:
    assert await rpc.methods.sum([1, 2, 3]) == 6
    assert await rpc.methods.zip(['a', 'b'], [1, 2]) == [['a', 1], ['b', 2]]
```

**Example with the decorator:**
```python
import aiohttp_rpc
from aiohttp import web

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

**It is possible to pass extra HTTP parameters to aiohttp via `direct_call`/`direct_batch`:**

```python
import aiohttp_rpc


jsonrpc_request = aiohttp_rpc.JSONRPCRequest(method_name='test', params={'test_value': 1})
async with aiohttp_rpc.JSONRPCClient('/rpc') as rpc:
    await rpc.direct_call(
        jsonrpc_request,
        headers={'X-Custom-Header': 'custom value'},
        timeout=10,
    )
```

[back to top](#table-of-contents)

---


## License
MIT
