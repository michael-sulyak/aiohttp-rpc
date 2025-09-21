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

### pip
```sh
pip install aiohttp-rpc
```

## Usage

### HTTP Server Example

```python
from aiohttp import web
import aiohttp_rpc


def echo(*args, **kwargs):
    return {'args': args, 'kwargs': kwargs}

# If a method accepts a parameter named "rpc_request",
# add it with pass_extra_kwargs=True and use inject_request_middleware
# (included in DEFAULT_MIDDLEWARES).
async def ping(rpc_request):
    return 'pong'


if __name__ == '__main__':
    # Pre-configured server with default middlewares.
    aiohttp_rpc.rpc_server.add_methods([
        aiohttp_rpc.JSONRPCMethod(ping, pass_extra_kwargs=True),
        echo,
    ])

    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_http_request),
    ])
    web.run_app(app, host='0.0.0.0', port=8080)
```

### HTTP Client Example

```python
import asyncio
import aiohttp_rpc


async def run():
    async with aiohttp_rpc.JSONRPCClient('http://0.0.0.0:8080/rpc') as rpc:
        # Idiomatic calls:
        print('#1', await rpc.methods.ping())                      # No args
        print('#2', await rpc.methods.echo('one', 'two'))          # Positional args
        print('#3', await rpc.methods.echo(three='3'))             # Keyword args

        # Lower-level calls:
        print('#4', await rpc.call('echo', three='3'))
        await rpc.notify('echo', 123)                              # Notification

        # Direct call returns a JSONRPCResponse object:
        resp = await rpc.direct_call(aiohttp_rpc.JSONRPCRequest(id=123, method_name='ping'))
        print('#5', resp)

        # Batch calls (order preserved by default):
        print('#6', await rpc.batch(
            rpc.methods.ping.request(),
            rpc.methods.echo.request('one', 'two'),
            rpc.methods.echo.request(three='3'),
        ))

        # Fire-and-forget batch notifications:
        await rpc.batch_notify(
            rpc.methods.ping.notification(),
            rpc.methods.echo.notification('one', 'two'),
            rpc.methods.echo.notification(three='3'),
        )


asyncio.run(run())
```

This prints:
```text
#1 pong
#2 {'args': ['one', 'two'], 'kwargs': {}}
#3 {'args': [], 'kwargs': {'three': '3'}}
#4 {'args': [], 'kwargs': {'three': '3'}}
#5 JSONRPCResponse(id=123, jsonrpc='2.0', result='pong', error=None, context={'http_response': ...})
#6 ('pong', {'args': ['one', 'two'], 'kwargs': {}}, {'args': [], 'kwargs': {'three': '3'}})
```

[back to top](#table-of-contents)

---

## Integration

Need to serialize non-JSON types? Provide a custom serializer:

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
        return {'uuid': str(value.uuid), 'username': value.username, 'email': value.email}
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
```

Convert incoming custom types with middleware:

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


# Middleware that converts arguments before the method call.
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
```

[back to top](#table-of-contents)

---

## Middleware

Middleware has an interface similar to aiohttp’s web middleware:

```python
import aiohttp_rpc
import typing


async def simple_middleware(request: aiohttp_rpc.JSONRPCRequest,
                            handler: typing.Callable) -> aiohttp_rpc.JSONRPCResponse:
    # Before the method (and downstream middleware)
    response = await handler(request)
    # After the method
    return response


rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[
    aiohttp_rpc.middlewares.exception_middleware,
    simple_middleware,
])
```

Included middlewares:
- exception_middleware — catches exceptions, converts to JSON-RPC errors (logging included).
- inject_request_middleware — stores the request object in extra kwargs as "rpc_request". Methods receive it only if added with pass_extra_kwargs=True.
- logging_middleware — logs raw JSON-RPC requests and responses.
- inject_ws_client_middleware — on WS server, attaches a WS client to the request so your method can send JSON-RPC messages back over the same socket (see below).
- check_origins(allowed_origins) — factory returning middleware that permits only the listed HTTP Origin values (for HTTP endpoints).

DEFAULT_MIDDLEWARES:
```python
DEFAULT_MIDDLEWARES = (
    exception_middleware,
    inject_request_middleware,
)
```

You can also use aiohttp web middlewares for web.Request/web.Response processing.

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
        # allowed_origins={'https://example.com'},  # optional Origin check
    )
    rpc_server.add_methods([
        aiohttp_rpc.JSONRPCMethod(ping, pass_extra_kwargs=True),
        echo,
    ])

    app = web.Application()
    app.router.add_routes([
        web.get('/rpc', rpc_server.handle_http_request),
    ])
    app.on_shutdown.append(rpc_server.on_shutdown)
    web.run_app(app, host='0.0.0.0', port=8080)
```

Options:
- allowed_origins: an optional container of allowed Origin values. Requests with other origins get HTTP 403.
- json_response_handler: optional callback invoked if the server receives a response-shaped message (useful if the server also acts as a client over the same connection).
- ws_response_cls / ws_response_kwargs: customize the WebSocketResponse class and options (default max_msg_size is 1_048_576 bytes).

### WS Client Example

```python
import asyncio
import aiohttp_rpc


async def run():
    async with aiohttp_rpc.WSJSONRPCClient('http://0.0.0.0:8080/rpc') as rpc:
        print(await rpc.methods.ping())
        print(await rpc.methods.echo('request'))          # args
        await rpc.methods.echo.notify('notification')     # notification (no response)
        print(rpc.methods.echo.request('some request'))   # JSONRPCRequest for batching
        print(rpc.methods.echo.notification(a=1))         # JSONRPCRequest without id
        await rpc.notify('ping')                          # returns None
        print(await rpc.batch(
            rpc.methods.echo.request('test'),
            rpc.methods.echo.notification(a=1, b=2),
            rpc.methods.ping.request(),
        ))


asyncio.run(run())
```

### Server-initiated messages over the same WS

To allow a method to send JSON-RPC requests back to the client over the same WebSocket connection, enable the middleware and declare the parameter:

```python
import aiohttp_rpc

async def server_push(ws_rpc_client):  # <-- added by middleware
    # call back to the connected client:
    return await ws_rpc_client.call('client_method', 42)

rpc_server = aiohttp_rpc.WSJSONRPCServer(
    middlewares=[
        aiohttp_rpc.middlewares.exception_middleware,
        aiohttp_rpc.middlewares.inject_request_middleware,
        aiohttp_rpc.middlewares.inject_ws_client_middleware,  # attaches ws_rpc_client
    ],
)
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(server_push, pass_extra_kwargs=True))
```

[back to top](#table-of-contents)

---

## API Reference

### server

- class JSONRPCServer(BaseJSONRPCServer)
  - def __init__(self, *, json_serialize=json_serialize, json_deserialize=json_deserialize, middlewares=(), methods=None, max_batch=None)
  - def add_method(self, method, *, replace=False) -> JSONRPCMethod
  - def add_methods(self, methods, *, replace=False) -> Tuple[JSONRPCMethod, ...]
  - async def handle_http_request(self, http_request: web.Request) -> web.Response

- class WSJSONRPCServer(BaseJSONRPCServer)
  - def __init__(..., allowed_origins: Optional[Container[str]] = None, json_response_handler: Optional[Callable] = None, ws_response_cls=WebSocketResponse, ws_response_kwargs=None)
  - async def handle_http_request(self, http_request: web.Request) -> web.StreamResponse
  - async def on_shutdown(self, app: web.Application) -> None

- rpc_server: JSONRPCServer (pre-configured with DEFAULT_MIDDLEWARES)

### client

- class JSONRPCClient(BaseJSONRPCClient)
  - def __init__(self, url, *, session: Optional[aiohttp.ClientSession] = None, json_serialize=json_serialize, json_deserialize=json_deserialize, **request_kwargs)
    - request_kwargs are passed to ClientSession(...)
  - async def connect() -> None
  - async def disconnect() -> None
  - async def call(self, method: str, *args, **kwargs) -> Any
  - async def notify(self, method: str, *args, **kwargs) -> None
  - async def batch(self, *requests, save_order: bool = True) -> Sequence
  - async def batch_notify(self, *requests) -> None
  - async def direct_call(self, request: JSONRPCRequest, **request_kwargs) -> Optional[JSONRPCResponse]
  - async def direct_batch(self, batch_request: JSONRPCBatchRequest, **request_kwargs) -> Optional[JSONRPCBatchResponse]
    - request_kwargs go to aiohttp.ClientSession.post(...)
    - On success, response.context contains {'http_response': aiohttp.ClientResponse}

- class WSJSONRPCClient(BaseJSONRPCClient)
  - def __init__(self, url: Optional[str] = None, *, session: Optional[aiohttp.ClientSession] = None, ws_connect: Optional[WSConnectType] = None, timeout: Optional[float] = 60, timeout_for_data_receiving: Optional[float] = 60, connection_check_interval: Optional[float] = 5, json_requests_handler: Optional[WSJSONRequestsHandler] = None, unprocessed_json_responses_handler: Optional[UnprocessedWSJSONResponsesHandler] = None, json_serialize=json_serialize, json_deserialize=json_deserialize, **ws_connect_kwargs)
  - async def connect() -> None
  - async def disconnect() -> None
  - Same high-level API as HTTP client; errors include RequestTimeoutError, TransportError, ServerError.

- Common to both clients
  - constructor arg error_map: Mapping[int, Type[JSONRPCError]] (default: DEFAULT_KNOWN_ERRORS_MAP) for mapping server error codes to custom exception types.
  - methods: JSONRPCClientMethods — dynamic attribute access for remote methods with helpers:
    - await rpc.methods.method_name(...)
    - await rpc.methods.method_name.notify(...)
    - rpc.methods.method_name.request(...) -> JSONRPCRequest
    - rpc.methods.method_name.notification(...) -> JSONRPCRequest (no id)

### protocol

- class JSONRPCRequest
  - id: Union[int, str, None]; method_name: str; jsonrpc: str; extra_kwargs: MutableMapping; context: MutableMapping
  - params: Any; args: Optional[Sequence]; kwargs: Optional[Mapping]
  - is_notification: bool
  - methods: set_params(...), set_args_and_kwargs(...), dump(), load(...)

- class JSONRPCResponse
  - id: Union[int, str, None]; jsonrpc: str; result: Any; error: Optional[JSONRPCError]; context: MutableMapping
  - dump(), load(...)

- class JSONRPCBatchResponse
  - responses: Tuple[JSONRPCResponse, ...]; dump(), load(...)

- class JSONRPCMethod(BaseJSONRPCMethod)
  - def __init__(self, func, *, name=None, pass_extra_kwargs=False, prepare_result=None)
    - prepare_result can be sync or async; if provided, it post-processes the method result.

- class JSONRPCUnlinkedResults / JSONRPCDuplicatedResults
  - Utilities used by collect_batch_result.

### decorators

- def rpc_method(name: Optional[str] = None, *, rpc_server=default_rpc_server, pass_extra_kwargs=True, prepare_result=None)
  - Registers the function on the default HTTP rpc_server at import time.

### errors

- class JSONRPCError(RuntimeError)
- class ServerError(JSONRPCError)
- class ParseError(JSONRPCError)
- class InvalidRequest(JSONRPCError)
- class MethodNotFound(JSONRPCError)
- class InvalidParams(JSONRPCError)
- class InternalError(JSONRPCError)
- Client-side errors:
  - EmptyResponse
  - RequestTimeoutError
  - TransportError
  - HTTPStatusError
- DEFAULT_KNOWN_ERRORS and DEFAULT_KNOWN_ERRORS_MAP

### middlewares

- exception_middleware(request, handler) -> JSONRPCResponse
- inject_request_middleware(request, handler) -> JSONRPCResponse
- logging_middleware(request, handler) -> JSONRPCResponse
- inject_ws_client_middleware(request, handler) -> JSONRPCResponse
- check_origins(allowed_origins) -> middleware
- DEFAULT_MIDDLEWARES

### utils

- json_serialize(value) -> str
- json_deserialize(text) -> Any
- convert_params_to_args_and_kwargs(params) -> Tuple[Sequence, Mapping]
- parse_args_and_kwargs(args, kwargs) -> Tuple[Any, Sequence, Mapping]
- get_random_id() -> str
- collect_batch_result(batch_request, batch_response) -> Tuple[Any, ...]

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
rpc_server.add_method(ping_1, replace=True)
rpc_server.add_methods([ping_1, ping_2], replace=True)

# Receive "rpc_request" (requires inject_request_middleware):
async def ping_with_request(rpc_request): return 'pong with request'
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(ping_with_request, pass_extra_kwargs=True))
```

Built-ins:

```python
# Server
import aiohttp_rpc

rpc_server = aiohttp_rpc.JSONRPCServer(middlewares=[aiohttp_rpc.middlewares.inject_request_middleware])
rpc_server.add_method(sum)
rpc_server.add_method(aiohttp_rpc.JSONRPCMethod(zip, prepare_result=list))

# Client
# async with aiohttp_rpc.JSONRPCClient('/rpc') as rpc:
#     assert await rpc.methods.sum([1, 2, 3]) == 6
#     assert await rpc.methods.zip(['a', 'b'], [1, 2]) == [['a', 1], ['b', 2]]
```

Decorator:

```python
import aiohttp_rpc
from aiohttp import web

@aiohttp_rpc.rpc_method()  # pass_extra_kwargs=True by default
def echo(*args, **kwargs):
    return {'args': args, 'kwargs': kwargs}

if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes([
        web.post('/rpc', aiohttp_rpc.rpc_server.handle_http_request),
    ])
    web.run_app(app, host='0.0.0.0', port=8080)
```

Pass extra aiohttp parameters for HTTP requests:

```python
import aiohttp_rpc
from aiohttp import ClientTimeout

jsonrpc_request = aiohttp_rpc.JSONRPCRequest(method_name='test', params={'test_value': 1})

async with aiohttp_rpc.JSONRPCClient('http://0.0.0.0:8080/rpc') as rpc:
    await rpc.direct_call(
        jsonrpc_request,
        headers={'X-Custom-Header': 'custom value'},
        timeout=ClientTimeout(total=10),  # forwarded to aiohttp.ClientSession.post(...)
    )
```

[back to top](#table-of-contents)

---

## License
MIT
