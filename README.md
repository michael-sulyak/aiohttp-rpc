# aiohttp-rpc

[![PyPI](https://img.shields.io/pypi/v/aiohttp-rpc.svg?style=flat)](https://pypi.org/project/aiohttp-rpc/)
[![PyPI - Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?style=flat)](https://www.python.org/downloads/release/python-3136/)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/expert-m/aiohttp-rpc.svg?style=flat)](https://scrutinizer-ci.com/g/expert-m/aiohttp-rpc/?branch=master)
[![GitHub Issues](https://img.shields.io/github/issues/expert-m/aiohttp-rpc.svg?style=flat)](https://github.com/expert-m/aiohttp-rpc/issues)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat)](https://opensource.org/licenses/MIT)

> A library for simple integration of the [JSON-RPC 2.0 protocol](https://www.jsonrpc.org/specification) into a Python application using [aiohttp](https://github.com/aio-libs/aiohttp).  
> The goal is to provide a simple, fast, and reliable way to add JSON-RPC 2.0 to your app on the server and/or client side.
>
> The library has only one dependency:
> - [aiohttp](https://github.com/aio-libs/aiohttp) — async HTTP client/server framework

## Table Of Contents
- [Installation](#installation)
  - [pip](#pip)
- [Usage](#usage)
  - [HTTP Server Example](#http-server-example)
  - [HTTP Client Example](#http-client-example)
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

# If a method accepts a parameter named "rpc_request",
# make sure the method is added with pass_extra_kwargs=True
# and the server uses inject_request_middleware (included in DEFAULT_MIDDLEWARES).
async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    aiohttp_rpc.rpc_server.add_methods([
        # Ensure "rpc_request" is injected:
        aiohttp_rpc.JSONRPCMethod(ping, pass_extra_kwargs=True),
        echo,
    ])

    # Optional: adds "get_methods" and "get_method" introspection methods.
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
        # Idiomatic calls:
        print('#1', await rpc.methods.ping())  # Call without arguments.
        print('#2', await rpc.methods.echo('one', 'two'))  # Positional args.
        print('#3', await rpc.methods.echo(three='3'))  # Keyword args (use either args or kwargs, not both).
        # Note: if the server returns an error, an exception is raised.

        # Lower-level calls:
        print('#4', await rpc.call('echo', three='3'))
        print('#5', await rpc.notify('echo', 123))
        print('#7', await rpc.direct_call(aiohttp_rpc.JSONRPCRequest(id=123, method_name='ping')))

        # Batch calls:
        print('#8', await rpc.batch(
            rpc.methods.ping.request(),                   # Returns JSONRPCRequest with a generated id.
            rpc.methods.echo.request('one', 'two'),
            rpc.methods.echo.request(three='3'),
        ))
        print('#9', await rpc.batch_notify(               # Does not wait for responses.
            rpc.methods.ping.notification(),              # Returns JSONRPCRequest without "id".
            rpc.methods.echo.notification('one', 'two'),
            rpc.methods.echo.notification(three='3'),
        ))
        # Note: if one response in the batch is an error, the result list contains a JSONRPCError instance at that position.

        # Introspection:
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
#10 {'ping': {'doc': None, 'args': [], 'kwargs': []}, 'echo': {'doc': None, 'args': [], 'kwargs': []}, 'get_method': {'doc': None, 'args': ['name'], 'kwargs': []}, 'get_methods': {'doc': None, 'args': [], 'kwargs': []}}
```

[back to top](#table-of-contents)

---

<p align="center"><b>↑ This is enough to start :sunglasses: ↑</b></p>

---

## Integration

This library should simplify your life, not complicate it.

Existing functions may return objects that are not JSON-serializable — that’s easy to fix by supplying a custom serializer:

```python
from aiohttp import web
import aiohttp_rpc
import uuid
import json
from dataclasses import dataclass
from functools import partial


@dataclass
class User:  # Not JSON-serializable by default.
    uuid: uuid.UUID
    username: str = 'mike'
    email: str = 'some@mail.com'


async def get_user_by_uuid(user_uuid) -> User:
    # For example, data may come from a database.
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

You can also accept custom types by converting them in middleware:

```python
# RPC method that takes a custom type.
def generate_user_token(user: User):
    return f'token-{str(user.uuid).split("-")[0]}'


async def replace_type(data):
    if not isinstance(data, dict) or '__type__' not in data:
        return data

    if data['__type__'] == 'user':
        return await get_user_by_uuid(data['uuid'])

    raise aiohttp_rpc.errors.InvalidParams


# Middleware that converts types before the method is called.
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

Middleware lets you adapt arguments, results, and more.  
If you need permission checks per method, you can override JSONRPCMethod or write middleware.

[back to top](#table-of-contents)

---

## Middleware

Middleware processes JSON-RPC requests and responses and has an interface similar to [aiohttp middleware](https://docs.aiohttp.org/en/stable/web_advanced.html#middlewares).

```python
import aiohttp_rpc
import typing


async def simple_middleware(request: aiohttp_rpc.JSONRPCRequest,
                            handler: typing.Callable) -> aiohttp_rpc.JSONRPCResponse:
    # Runs before the method (and downstream middleware).
    response = await handler(request)
    # Runs after the method.
    return response


rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[
    aiohttp_rpc.middlewares.exception_middleware,
    simple_middleware,
])
```

Note about injecting the request object:
- inject_request_middleware stores the JSON-RPC request object as extra kwargs under the name "rpc_request".
- Methods receive these extra kwargs only if they were added with pass_extra_kwargs=True (e.g., via JSONRPCMethod(..., pass_extra_kwargs=True) or the @rpc_method decorator, which defaults to pass_extra_kwargs=True).

You can also use aiohttp middlewares to process web.Request/web.Response.

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
    rpc_server.add_methods([
        aiohttp_rpc.JSONRPCMethod(ping, pass_extra_kwargs=True),  # to receive "rpc_request"
        echo,
    ])

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
        print(await rpc.methods.ping())                      # Request + wait for response.
        print(await rpc.methods.echo('request'))            # Positional args.
        await rpc.methods.echo.notify('notification')       # Notification (no response expected).
        print(rpc.methods.echo.request('some request'))     # Build a JSONRPCRequest for batching.
        print(rpc.methods.echo.notification('some notification'))  # Notification object (no id).
        print(await rpc.notify('ping'))                     # None
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

### server
- class JSONRPCServer(BaseJSONRPCServer)
  - def __init__(self, *, json_serialize=json_serialize, middlewares=(), methods=None, max_batch=None, max_payload_bytes=1_048_576)
  - def add_method(self, method, *, replace=False) -> JSONRPCMethod
  - def add_methods(self, methods, replace=False) -> Tuple[JSONRPCMethod, ...]
  - def add_introspection(self) -> None
  - def get_method(self, name) -> Optional[Mapping]
  - def get_methods(self) -> Mapping[str, Mapping]
  - async def handle_http_request(self, http_request: web.Request) -> web.Response

- class WSJSONRPCServer(BaseJSONRPCServer)
  - async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse
  - async def on_shutdown(self, app: web.Application) -> None

- rpc_server: JSONRPCServer (pre-configured with DEFAULT_MIDDLEWARES)

### client
- class JSONRPCClient(BaseJSONRPCClient)
  - async def connect(self) -> None
  - async def disconnect(self) -> None
  - async def call(self, method: str, *args, **kwargs)
  - async def notify(self, method: str, *args, **kwargs) -> None
  - async def batch(self, *requests, save_order: bool = True) -> Sequence
  - async def batch_notify(self, *requests) -> None
  - async def direct_call(self, request: JSONRPCRequest, **request_kwargs) -> Optional[JSONRPCResponse]
  - async def direct_batch(self, batch_request: JSONRPCBatchRequest, **request_kwargs) -> Optional[JSONRPCBatchResponse]
  - methods: JSONRPCClientMethods (dynamic attribute access to remote methods)

- class WSJSONRPCClient(BaseJSONRPCClient) — same high-level API as the HTTP client, over WebSockets.

### protocol
- class JSONRPCRequest
  - id: Union[int, str, None]
  - method_name: str
  - jsonrpc: str
  - extra_kwargs: MutableMapping
  - context: MutableMapping
  - params: Any
  - args: Optional[Sequence]
  - kwargs: Optional[Mapping]
  - is_notification: bool

- class JSONRPCResponse
  - id: Union[int, str, None]
  - jsonrpc: str
  - result: Any
  - error: Optional[JSONRPCError]
  - context: MutableMapping

- class JSONRPCMethod(BaseJSONRPCMethod)
  - def __init__(self, func, *, name=None, pass_extra_kwargs=False, prepare_result=None)

- class JSONRPCUnlinkedResults
- class JSONRPCDuplicatedResults

### decorators
- def rpc_method(name: Optional[str] = None, *, rpc_server=default_rpc_server, pass_extra_kwargs=True, prepare_result=None)

### errors
- class JSONRPCError(RuntimeError)
- class ServerError(JSONRPCError)
- class ParseError(JSONRPCError)
- class InvalidRequest(JSONRPCError)
- class MethodNotFound(JSONRPCError)
- class InvalidParams(JSONRPCError)
- class InternalError(JSONRPCError)
- class EmptyResponse(JSONRPCError)                # client-side (no response received)
- class RequestTimeoutError(JSONRPCError)          # client-side (response timed out)
- class TransportError(JSONRPCError)               # client-side (send failed)
- class HTTPStatusError(JSONRPCError)              # client-side (non-2xx with no parseable JSON)
- DEFAULT_KNOWN_ERRORS

### middlewares
- async def inject_request_middleware(request, handler) — puts the request object into extra kwargs under "rpc_request"; to pass it to your method, add the method with pass_extra_kwargs=True.
- async def exception_middleware(request, handler) — converts exceptions to JSON-RPC errors.
- async def logging_middleware(request, handler) — logs raw requests and responses.
- async def inject_ws_client_middleware(request, handler) — attaches a WS client to context for server-initiated messages on the same socket.
- DEFAULT_MIDDLEWARES = (exception_middleware, inject_request_middleware)

### utils
- def json_serialize(value) -> str
- def convert_params_to_args_and_kwargs(params) -> Tuple[Sequence, Mapping]
- def parse_args_and_kwargs(args, kwargs) -> Tuple[Any, Sequence, Mapping]
- def get_random_id() -> str
- def collect_batch_result(batch_request, batch_response) -> Tuple[Any, ...]

### constants
- NOTHING
- VERSION_2_0

[back to top](#table-of-contents)

---

## More examples

The library lets you add methods in several ways:

```python
import aiohttp_rpc

def ping_1(): return 'pong 1'
def ping_2(): return 'pong 2'
def ping_3(): return 'pong 3'

rpc_server = aiohttp_rpc.JSONRPCServer()
rpc_server.add_method(ping_1)                                      # 'ping_1'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_2))           # 'ping_2'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_3, name='third_ping'))  # 'third_ping'
rpc_server.add_methods([ping_3])                                   # 'ping_3'

# Replace methods:
rpc_server.add_method(ping_1, replace=True)                        # 'ping_1'
rpc_server.add_methods([ping_1, ping_2], replace=True)             # 'ping_1', 'ping_2'

# If a method needs "rpc_request", add with pass_extra_kwargs=True and enable inject_request_middleware:
async def ping_with_request(rpc_request): return 'pong with request'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_with_request, pass_extra_kwargs=True))
```

Example with built-ins:

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

Example with the decorator:
```python
import aiohttp_rpc
from aiohttp import web

@aiohttp_rpc.rpc_method()  # pass_extra_kwargs=True by default
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

Pass extra HTTP parameters to aiohttp via direct_call/direct_batch:

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
