import typing

from aiohttp import client_ws, web_ws


if typing.TYPE_CHECKING:
    from . import protocol  # NOQA

JsonRpcIdType = typing.Union[int, str]
JSONEncoderType = typing.Callable[[typing.Any], str]
UnboundJSONEncoderType = typing.Callable[[typing.Any], str]
SingleRequestProcessorType = typing.Callable[['protocol.JsonRpcRequest'], typing.Awaitable['protocol.JsonRpcResponse']]
UnboundSingleRequestProcessorType = typing.Callable[
    [typing.Any, 'protocol.JsonRpcRequest'],
    typing.Awaitable['protocol.JsonRpcResponse'],
]

ClientMethodDescriptionType = typing.Union[str, typing.Sequence, 'protocol.JsonRpcRequest']
ClientMethodDescriptionsType = typing.Union[
    typing.Iterable[ClientMethodDescriptionType],
    'protocol.JsonRpcBatchRequest',
]

ServerMethodDescriptionType = typing.Union['protocol.BaseJsonRpcMethod', typing.Callable]

WSConnectType = typing.Union[client_ws.ClientWebSocketResponse, web_ws.WebSocketResponse]
