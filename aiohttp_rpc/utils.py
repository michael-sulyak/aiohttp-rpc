import json
import typing
import uuid
from functools import partial
from traceback import format_exception_only

from . import constants, errors


__all__ = (
    'convert_params_to_args_and_kwargs',
    'parse_args_and_kwargs',
    'get_exc_message',
    'json_serialize',
)


def convert_params_to_args_and_kwargs(params: typing.Any) -> typing.Tuple[list, dict]:
    if params is constants.NOTHING:
        return [], {}

    if isinstance(params, constants.JSON_PRIMITIVE_TYPES):
        return [params], {}

    if isinstance(params, list):
        return params, {}

    if isinstance(params, dict):
        return [], params

    raise errors.InvalidParams('Params have unsupported data types.')


def parse_args_and_kwargs(args: typing.Any, kwargs: typing.Any) -> typing.Tuple:
    has_args = bool(args and args is not constants.NOTHING)
    has_kwargs = bool(kwargs and kwargs is not constants.NOTHING)

    if not has_args and not has_kwargs:
        return constants.NOTHING, [], {}

    if not (has_args ^ has_kwargs):
        raise errors.InvalidParams('Need use args or kwargs.')

    if has_args:
        args = list(args)

        if len(args) == 1 and isinstance(args[0], constants.JSON_PRIMITIVE_TYPES):
            return args[0], args, {}

        return args, args, {}

    kwargs = dict(kwargs)
    return kwargs, [], kwargs


def get_random_id() -> str:
    return str(uuid.uuid4())


def get_exc_message(exp: Exception) -> str:
    return ''.join(format_exception_only(exp.__class__, exp)).strip()


def validate_jsonrpc(jsonrpc: typing.Any) -> None:
    if jsonrpc != constants.VERSION_2_0:
        raise errors.InvalidRequest(f'Only version "{constants.VERSION_2_0}" is supported.')


json_serialize = partial(json.dumps, default=lambda x: repr(x))


# def is_json_rpc_request(data: typing.Any) -> bool:
#     if isinstance(data, dict) and 'method' in data:
#         return True
#
#     if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and 'method' in data[0]:
#         return True
#
#     return False


# def is_json_rpc_response(data: typing.Any) -> bool:
#     if isinstance(data, dict) and ('result' in data or 'error' in data):
#         return True
#
#     if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and ('result' in data[0] or 'error' in data[0]):
#         return True
#
#     return False


# def is_json_batch(data: typing.Any) -> bool:
#     return isinstance(data, list)


# class WebSocketConnection:
#     _ws_connect: WSConnectType
#     _message_worker: typing.Optional[asyncio.Future] = None
#     _handlers: typing.List[typing.Callable]
#
#     def __init__(self, ws_connect: WSConnectType) -> None:
#         self._ws_connect = ws_connect
#         self._handlers = []
#
#     def add_handler(self, handler: typing.Callable) -> None:
#         self._handlers.append(handler)
#
#     async def open(self) -> None:
#         self._message_worker = asyncio.ensure_future(self._handle_ws_messages())
#
#     async def close(self) -> None:
#         await self._ws_connect.close()
#
#         if self._message_worker:
#             await self._message_worker
#
#     @property
#     def closed(self) -> bool:
#         return self._ws_connect.closed
#
#     async def send_str(self, message: typing.Union[str, bytes]) -> None:
#         await self._ws_connect.send_str(message)
#
#     async def _handle_ws_messages(self):
#         async for ws_msg in self._ws_connect:
#             if ws_msg.type == http_websocket.WSMsgType.BINARY:
#                 raw_data = ws_msg.data.decode()
#             elif ws_msg.type == http_websocket.WSMsgType.TEXT:
#                 raw_data = ws_msg.data
#             else:
#                 continue
#
#             parsed_data, exception = self._parse_raw_data(raw_data)
#
#             if exception is not None:
#                 await self._call_handlers(
#                     parsed_data=parsed_data,
#                     prepared_data=None,
#                     exception=exception,
#                 )
#                 return
#
#             try:
#                 prepared_data = self._prepare_data(parsed_data)
#             except Exception as e:
#                 await self._call_handlers(
#                     parsed_data=parsed_data,
#                     prepared_data=None,
#                     exception=e,
#                 )
#                 return
#
#             await self._call_handlers(
#                 parsed_data=parsed_data,
#                 prepared_data=prepared_data,
#                 exception=None,
#             )
#
#     async def _call_handlers(self, **kwargs) -> None:
#         for handler in self._handlers:
#             await handler(**kwargs)
#
#     @staticmethod
#     def _parse_raw_data(raw_data: str) -> typing.Tuple:
#         try:
#             input_data = json.loads(raw_data)
#         except json.JSONDecodeError as e:
#             exception = e
#             input_data = None
#         else:
#             exception = None
#
#         return input_data, exception
#
#     @staticmethod
#     def _prepare_data(parsed_data):
#         from . import protocol, errors
#
#         if is_json_rpc_response(parsed_data):
#             if is_json_batch(parsed_data):
#                 return protocol.JsonRpcBatchResponse.from_list(parsed_data)
#             else:
#                 return protocol.JsonRpcResponse.from_dict(parsed_data)
#         elif is_json_rpc_request(parsed_data):
#             if is_json_batch(parsed_data):
#                 return protocol.JsonRpcBatchRequest.from_list(parsed_data)
#             else:
#                 return protocol.JsonRpcRequest.from_dict(parsed_data)
#         else:
#             raise errors.ParseError
