import typing


if typing.TYPE_CHECKING:
    from . import protocol  # NOQA

JSONEncoderType = typing.Callable[[typing.Any], str]
SingleRequestProcessorType = typing.Callable[['protocol.JsonRpcRequest'], typing.Awaitable['protocol.JsonRpcResponse']]
