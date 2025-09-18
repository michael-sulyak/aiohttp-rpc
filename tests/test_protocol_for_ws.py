# https://www.jsonrpc.org/specification#examples
import asyncio

import pytest
from aiohttp import web

import aiohttp_rpc
from aiohttp_rpc import errors
from tests import utils


async def test_rpc_call_with_positional_parameters(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}
    <-- {"jsonrpc": "2.0", "result": 19, "id": 1}

    --> {"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}
    <-- {"jsonrpc": "2.0", "result": -19, "id": 2}
    """

    def subtract(a, b):
        return a - b

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(subtract)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.methods.subtract(42, 23) == 19
        assert await rpc.methods.subtract(23, 42) == -19

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'subtract', 'params': [42, 23], 'id': 1})
        assert result[0] == {'jsonrpc': '2.0', 'result': 19, 'id': 1}

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'subtract', 'params': [23, 42], 'id': 2})
        assert result[0] == {'jsonrpc': '2.0', 'result': -19, 'id': 2}


async def test_rpc_call_with_named_parameters(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}
    <-- {"jsonrpc": "2.0", "result": 19, "id": 3}

    --> {"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}
    <-- {"jsonrpc": "2.0", "result": 19, "id": 4}
    """

    def subtract(*, subtrahend, minuend):
        return minuend - subtrahend

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(subtract)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.methods.subtract(subtrahend=23, minuend=42) == 19
        assert await rpc.methods.subtract(minuend=42, subtrahend=23) == 19

        result = await rpc.send_json({
            'jsonrpc': '2.0', 'method': 'subtract', 'params': {"subtrahend": 23, "minuend": 42}, 'id': 3,
        })
        assert result[0] == {'jsonrpc': '2.0', 'result': 19, 'id': 3}

        result = await rpc.send_json({
            'jsonrpc': '2.0', 'method': 'subtract', 'params': {"minuend": 42, "subtrahend": 23}, 'id': 4
        })
        assert result[0] == {'jsonrpc': '2.0', 'result': 19, 'id': 4}


async def test_notification(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}
    --> {"jsonrpc": "2.0", "method": "foobar"}
    """

    def update(*args):
        return args

    def foobar(*args):
        return 'ok'

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(update)
    rpc_server.add_method(foobar)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.notify('update', subtrahend=23, minuend=42) is None
        assert await rpc.notify('foobar', minuend=42, subtrahend=23) is None

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'update', 'params': [1, 2, 3, 4, 5]})
        assert result[0] is None

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'foobar'})
        assert result[0] is None


async def test_rpc_call_of_non_existent_method(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "foobar", "id": "1"}
    <-- {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
    """

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        with pytest.raises(errors.MethodNotFound):
            assert await rpc.call('foobar', subtrahend=23, minuend=42)

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'foobar', 'id': '1'})
        assert result[0] == {
            'jsonrpc': '2.0', 'error': {'code': -32601, 'message': errors.MethodNotFound.message}, 'id': '1',
        }


async def test_rpc_call_with_invalid_json(aiohttp_client, mocker):
    """
    --> {"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]
    <-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}
    """

    rpc_server = aiohttp_rpc.WSJSONRPCServer()

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    future = asyncio.Future()

    async def unprocessed_json_response_handler(*, ws_connect, ws_msg, json_responses):
        future.set_result(json_responses)
        del json_responses[0]['error']['message']
        assert json_responses[0] == {'jsonrpc': '2.0', 'error': {'code': -32700}, 'id': None}

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
        unprocessed_json_responses_handler=unprocessed_json_response_handler,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )
        rpc._json_serialize = lambda x: x
        result = await rpc.send_json('{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]')
        assert result == (None, None,)
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()


async def test_rpc_call_with_an_empty_array(aiohttp_client, mocker):
    """
    --> []
    <-- []
    """

    rpc_server = aiohttp_rpc.WSJSONRPCServer()

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )

        with pytest.raises(errors.InvalidRequest):
            await rpc.batch()

        handle_ws_message.assert_not_called()

        assert await rpc.send_json([]) == (None, None,)
        handle_ws_message.assert_not_called()


async def test_rpc_call_with_an_invalid_batch(aiohttp_client, mocker):
    """
    --> [1]
    <-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    """

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)
    future = asyncio.Future()

    original_handle_ws_message = rpc_server._handle_ws_message

    async def _handle_ws_message(ws_msg, *args, **kwargs):
        await original_handle_ws_message(ws_msg, *args, **kwargs)
        assert ws_msg.data == '[1]'
        future.set_result(None)

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc_server,
            '_handle_ws_message',
            side_effect=_handle_ws_message,
        )
        assert await rpc.send_json([1]) == (None, None,)
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()


async def test_rpc_call_with_invalid_batch(aiohttp_client, mocker):
    """
    --> [1,2,3]
    <-- [
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    ]
    """

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)
    future = asyncio.Future()

    original_process_input_data = rpc_server._process_input_data

    async def _process_input_data(data, *args, **kwargs):
        assert data == [1, 2, 3]

        try:
            result = await original_process_input_data(data, *args, **kwargs)
        except Exception as e:
            result = e

        future.set_result(result)

        return result

    async with aiohttp_rpc.WSJSONRPCClient(
        '/rpc',
        session=client,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc_server,
            '_process_input_data',
            side_effect=_process_input_data,
        )
        await rpc.send_json([1, 2, 3])
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()

        result = tuple(response.dump() for response in future.result())

        assert result == ({
            'jsonrpc': '2.0',
            'error': {
                'code': -32600,
                'data': {'details': 'Data must be a dict.'},
                'message': 'Invalid Request',
            },
            'id': None,
        },) * 3


async def test_rpc_call_with_different_invalid_batch(aiohttp_client):
    """
    --> [
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
            {"foo": "boo"},
            {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
            {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
        ]
    <-- [
            {"jsonrpc": "2.0", "result": 7, "id": "1"},
            {"jsonrpc": "2.0", "result": 19, "id": "2"},
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
            {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "5"},
            {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
        ]
    """

    def subtract(a, b):
        return a - b

    def notify_hello(a):
        return a

    def get_data():
        return ['hello', 5]

    def my_sum(*args):
        return sum(args)

    rpc_server = aiohttp_rpc.WSJSONRPCServer()
    rpc_server.add_method(subtract)
    rpc_server.add_method((aiohttp_rpc.JSONRPCMethod(func=my_sum, name='sum')))
    rpc_server.add_method(notify_hello)
    rpc_server.add_method(get_data)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    called_methods = [
        aiohttp_rpc.JSONRPCRequest(id=1, method_name='sum', params=[1, 2, 4]),
        aiohttp_rpc.JSONRPCRequest(method_name='notify_hello', params=[1, 2, 4]),
        aiohttp_rpc.JSONRPCRequest(id=2, method_name='subtract', params=[42, 23]),
        aiohttp_rpc.JSONRPCRequest(id=5, method_name='foo.get', params={'name': 'myself'}),
        aiohttp_rpc.JSONRPCRequest(id=9, method_name='get_data'),
    ]

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.batch(*called_methods) == (7, None, 19, errors.MethodNotFound(), ['hello', 5],)
        assert await rpc.batch(*called_methods, save_order=False) == (7, 19, errors.MethodNotFound(), ['hello', 5],)

        result = await rpc.send_json([
            {'jsonrpc': '2.0', 'method': 'sum', 'params': [1, 2, 4], 'id': '1'},
            {'jsonrpc': '2.0', 'method': 'notify_hello', 'params': [7]},
            {'jsonrpc': '2.0', 'method': 'subtract', 'params': [42, 23], 'id': '2'},
            {'foo': 'boo'},
            {'jsonrpc': '2.0', 'method': 'foo.get', 'params': {'name': 'myself'}, 'id': '5'},
            {'jsonrpc': '2.0', 'method': 'get_data', 'id': '9'}
        ])

        assert result[0] == [
            {'jsonrpc': '2.0', 'result': 7, 'id': '1'},
            {'jsonrpc': '2.0', 'result': 19, 'id': '2'},
            {'jsonrpc': '2.0', 'error': {
                'code': -32600,
                'message': 'Invalid Request',
                'data': {'details': 'The request must contain "method" and "jsonrpc".'},
            }, 'id': None},
            {'jsonrpc': '2.0', 'error': {
                'code': -32601, 'message': 'Method not found'
            }, 'id': '5'},
            {'jsonrpc': '2.0', 'result': ['hello', 5], 'id': '9'},
        ]


async def test_ws_timeout_cleans_pending(aiohttp_client):
    async def sleep(a):
        await asyncio.sleep(a)
        return True

    server = aiohttp_rpc.WSJSONRPCServer()
    server.add_method(sleep)
    client = await utils.make_ws_client(aiohttp_client, server)

    async with aiohttp_rpc.WSJSONRPCClient('/rpc', session=client, timeout=0.05) as rpc:
        with pytest.raises(errors.RequestTimeoutError):
            await rpc.call('sleep', 0.2)

        assert len(rpc._pending) == 0  # no leaks


async def test_ws_allowed_origins(aiohttp_client):
    server = aiohttp_rpc.WSJSONRPCServer(allowed_origins={'https://good.example'})
    app = web.Application()
    app.router.add_get('/rpc', server.handle_http_request)
    app.on_shutdown.append(server.on_shutdown)
    client = await aiohttp_client(app)

    # Forbidden origin
    with pytest.raises(Exception):
        await client.ws_connect('/rpc', headers={'Origin': 'https://bad.example'})

    # Allowed origin
    ws = await client.ws_connect('/rpc', headers={'Origin': 'https://good.example'})
    await ws.close()
