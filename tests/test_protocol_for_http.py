# https://www.jsonrpc.org/specification#examples

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

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_method(subtract)

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
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

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_method(subtract)

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
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

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_method(update)
    rpc_server.add_method(foobar)

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        assert await rpc.notify('update', subtrahend=23, minuend=42) is None
        assert await rpc.notify('foobar', minuend=42, subtrahend=23) is None

        with pytest.raises(aiohttp_rpc.errors.EmptyResponse):
            await rpc.send_json({'jsonrpc': '2.0', 'method': 'update', 'params': [1, 2, 3, 4, 5]})

        with pytest.raises(aiohttp_rpc.errors.EmptyResponse):
            await rpc.send_json({'jsonrpc': '2.0', 'method': 'foobar'})

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'foobar'}, ignore_response=True)
        assert result[0] is None

        with pytest.raises(aiohttp_rpc.errors.EmptyResponse):
            # Note: The server must reply with a response, except for in the case of notifications.
            await rpc.send_json({'jsonrpc': '2.0', 'method': 'some_func'})


async def test_rpc_call_of_non_existent_method(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "foobar", "id": "1"}
    <-- {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
    """

    rpc_server = aiohttp_rpc.JSONRPCServer()

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        with pytest.raises(errors.MethodNotFound):
            assert await rpc.call('foobar', subtrahend=23, minuend=42)

        result = await rpc.send_json({'jsonrpc': '2.0', 'method': 'foobar', 'id': '1'})
        assert result[0] == {
            'jsonrpc': '2.0', 'error': {'code': -32601, 'message': errors.MethodNotFound.message}, 'id': '1',
        }


async def test_rpc_call_with_invalid_json(aiohttp_client):
    """
    --> {"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]
    <-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}
    """

    rpc_server = aiohttp_rpc.JSONRPCServer()

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        http_response = await rpc.session.post(
            rpc.url,
            data='{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]',
        )
        json_response = await http_response.json()
        del json_response['error']['message']

        assert json_response == {
            'jsonrpc': '2.0',
            'error': {'code': -32700, 'data': {'details': 'Invalid JSON'}},
            'id': None,
        }


async def test_rpc_call_with_an_empty_array(aiohttp_client):
    """
    --> []
    <-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": null}
    """

    rpc_server = aiohttp_rpc.JSONRPCServer()

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        with pytest.raises(errors.InvalidRequest):
            await rpc.batch()

        result = await rpc.send_json([])
        assert result[0] == {
            'jsonrpc': '2.0', 'error': {'code': -32600, 'message': 'Invalid Request'}, 'id': None,
        }


async def test_rpc_call_with_an_invalid_batch(aiohttp_client):
    """
    --> [1]
    <-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": null}
    """

    rpc_server = aiohttp_rpc.JSONRPCServer()

    client = await utils.make_client(aiohttp_client, rpc_server)

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        result = await rpc.send_json([1])
        assert result[0] == [{
            'jsonrpc': '2.0',
            'error': {'code': -32600, 'message': 'Invalid Request', 'data': {'details': 'Data must be a dict.'}},
            'id': None,
        }]


async def test_rpc_call_with_invalid_batch(aiohttp_client):
    """
    --> [1,2,3]
    <-- [
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": null},
      {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": null}
    ]
    """

    rpc_server = aiohttp_rpc.JSONRPCServer()

    client = await utils.make_client(aiohttp_client, rpc_server)

    json_with_error = {
        'jsonrpc': '2.0',
        'error': {
            'code': -32600,
            'message': 'Invalid Request',
            'data': {'details': 'Data must be a dict.'},
        },
        'id': None,
    }

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
        result = await rpc.send_json([1, 2, 3])
        assert result[0] == [json_with_error, json_with_error, json_with_error]


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

    rpc_server = aiohttp_rpc.JSONRPCServer()
    rpc_server.add_method(subtract)
    rpc_server.add_method((aiohttp_rpc.JSONRPCMethod(func=my_sum, name='sum')))
    rpc_server.add_method(notify_hello)
    rpc_server.add_method(get_data)

    client = await utils.make_client(aiohttp_client, rpc_server)

    called_methods = [
        aiohttp_rpc.JSONRPCRequest(id=1, method_name='sum', params=[1, 2, 4]),
        aiohttp_rpc.JSONRPCRequest(method_name='notify_hello', params=[1, 2, 4]),
        aiohttp_rpc.JSONRPCRequest(id=2, method_name='subtract', params=[42, 23]),
        aiohttp_rpc.JSONRPCRequest(id=5, method_name='foo.get', params={'name': 'myself'}),
        aiohttp_rpc.JSONRPCRequest(id=9, method_name='get_data'),
    ]

    async with aiohttp_rpc.JSONRPCClient('/rpc', session=client) as rpc:
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
