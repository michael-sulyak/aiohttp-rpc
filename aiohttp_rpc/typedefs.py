import typing

from aiohttp import client_ws, web_ws


if typing.TYPE_CHECKING:
    from . import protocol  # NOQA

JSONRPCIDType = typing.Union[int, str]
JSONEncoderType = typing.Callable[[typing.Any], str]
JSONDecoderType = typing.Callable[[str], typing.Any]
UnboundJSONEncoderType = JSONEncoderType
SingleRequestProcessorType = typing.Callable[['protocol.JSONRPCRequest'], typing.Awaitable['protocol.JSONRPCResponse']]
UnboundSingleRequestProcessorType = typing.Callable[
    [typing.Any, 'protocol.JSONRPCRequest'],
    typing.Awaitable['protocol.JSONRPCResponse'],
]
ServerMethodDescriptionType = typing.Union['protocol.BaseJSONRPCMethod', typing.Callable]
WSConnectType = typing.Union[client_ws.ClientWebSocketResponse, web_ws.WebSocketResponse]


class WSJSONRequestsHandler(typing.Protocol):
    async def __call__(self, *,
                       ws_connect: WSConnectType,
                       ws_msg: web_ws.WSMessage,
                       json_requests: typing.Sequence[typing.Mapping]) -> None:
        pass


class UnprocessedWSJSONResponsesHandler(typing.Protocol):
    async def __call__(self, *,
                       ws_connect: WSConnectType,
                       ws_msg: web_ws.WSMessage,
                       json_responses: typing.Sequence[typing.Mapping]) -> None:
        pass


class WSJSONResponseHandler(typing.Protocol):
    async def __call__(self, *,
                       ws_connect: WSConnectType,
                       ws_msg: web_ws.WSMessage,
                       json_response: typing.Mapping) -> None:
        pass
