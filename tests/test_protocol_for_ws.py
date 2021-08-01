# https://www.jsonrpc.org/specification#examples
import asyncio

import pytest

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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(subtract)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.subtract(42, 23) == 19
        assert await rpc.subtract(23, 42) == -19

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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(subtract)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.subtract(subtrahend=23, minuend=42) == 19
        assert await rpc.subtract(minuend=42, subtrahend=23) == 19

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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(update)
    rpc_server.add_method(foobar)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    future = asyncio.Future()

    def unprocessed_json_response_handler(*, ws_connect, ws_msg, json_response):
        future.set_result(json_response)
        del json_response['error']['message']
        assert json_response == {'jsonrpc': '2.0', 'error': {'code': -32700}, 'id': None}

    async with aiohttp_rpc.WsJsonRpcClient(
            '/rpc',
            session=client,
            unprocessed_json_response_handler=unprocessed_json_response_handler,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )
        rpc.json_serialize = lambda x: x
        result = await rpc.send_json('{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]')
        assert result == (None, None,)
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()


async def test_rpc_call_with_an_empty_array(aiohttp_client, mocker):
    """
    --> []
    <-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    """

    rpc_server = aiohttp_rpc.WsJsonRpcServer()

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    future = asyncio.Future()

    def unprocessed_json_response_handler(*, ws_connect, ws_msg, json_response):
        future.set_result(json_response)
        assert json_response == {
            'jsonrpc': '2.0', 'error': {'code': -32600, 'message': errors.InvalidRequest.message}, 'id': None,
        }

    async with aiohttp_rpc.WsJsonRpcClient(
            '/rpc',
            session=client,
            unprocessed_json_response_handler=unprocessed_json_response_handler,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )

        with pytest.raises(errors.InvalidRequest):
            await rpc.batch([])

        handle_ws_message.assert_not_called()
        await rpc.send_json([])
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()


async def test_rpc_call_with_an_invalid_batch(aiohttp_client, mocker):
    """
    --> [1]
    <-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
    """

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)
    future = asyncio.Future()

    def unprocessed_json_response_handler(*, ws_connect, ws_msg, json_response):
        future.set_result(json_response)
        assert json_response == {
            'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Data must be a dict.'}, 'id': None,
        }

    async with aiohttp_rpc.WsJsonRpcClient(
            '/rpc',
            session=client,
            unprocessed_json_response_handler=unprocessed_json_response_handler,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )
        await rpc.send_json([1])
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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    client = await utils.make_ws_client(aiohttp_client, rpc_server)
    future = asyncio.Future()

    json_with_error = {
        'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Data must be a dict or an list.'}, 'id': None,
    }

    def unprocessed_json_response_handler(*, ws_connect, ws_msg, json_response):
        future.set_result(json_response)
        assert json_response == [json_with_error, json_with_error, json_with_error]

    async with aiohttp_rpc.WsJsonRpcClient(
            '/rpc',
            session=client,
            unprocessed_json_response_handler=unprocessed_json_response_handler,
    ) as rpc:
        handle_ws_message = mocker.patch.object(
            rpc,
            '_handle_single_ws_message',
            side_effect=rpc._handle_single_ws_message,
        )
        await rpc.send_json([1, 2, 3])
        await asyncio.wait_for(future, timeout=3)
        handle_ws_message.assert_called_once()


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

    rpc_server = aiohttp_rpc.WsJsonRpcServer()
    rpc_server.add_method(subtract)
    rpc_server.add_method((aiohttp_rpc.JsonRpcMethod(func=my_sum, name='sum')))
    rpc_server.add_method(notify_hello)
    rpc_server.add_method(get_data)

    client = await utils.make_ws_client(aiohttp_client, rpc_server)

    called_methods = [
        aiohttp_rpc.JsonRpcRequest(id=1, method_name='sum', params=[1, 2, 4]),
        aiohttp_rpc.JsonRpcRequest(method_name='notify_hello', params=[1, 2, 4]),
        aiohttp_rpc.JsonRpcRequest(id=2, method_name='subtract', params=[42, 23]),
        aiohttp_rpc.JsonRpcRequest(id=5, method_name='foo.get', params={'name': 'myself'}),
        aiohttp_rpc.JsonRpcRequest(id=9, method_name='get_data'),
    ]

    async with aiohttp_rpc.WsJsonRpcClient('/rpc', session=client) as rpc:
        assert await rpc.batch(called_methods) == (7, None, 19, errors.MethodNotFound(), ['hello', 5],)
        assert await rpc.batch(called_methods, save_order=False) == (7, 19, errors.MethodNotFound(), ['hello', 5],)

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
                'code': -32600, 'message': 'The request must contain "method" and "jsonrpc".'
            }, 'id': None},
            {'jsonrpc': '2.0', 'error': {
                'code': -32601, 'message': 'The method does not exist / is not available.'
            }, 'id': '5'},
            {'jsonrpc': '2.0', 'result': ['hello', 5], 'id': '9'},
        ]
