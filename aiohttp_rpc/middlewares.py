import abc
import logging
import typing

from . import errors, protocol


if typing.TYPE_CHECKING:
    from . import server as rpc_server

__all__ = (
    'BaseJsonRpcMiddleware',
    'ExceptionMiddleware',
    'DEFAULT_MIDDLEWARES',
)

logger = logging.getLogger(__name__)


class BaseJsonRpcMiddleware(abc.ABC):
    server: 'rpc_server.JsonRpcServer'
    get_response: typing.Callable

    def __init__(self, server: 'rpc_server.JsonRpcServer', get_response: typing.Callable) -> None:
        self.server = server
        self.get_response = get_response

    @abc.abstractmethod
    async def __call__(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        # Code to be executed for each request before the method are called.

        response = await self.get_response(request)

        # Code to be executed for each request/response after the method is called.

        return response


class ExceptionMiddleware(BaseJsonRpcMiddleware):
    async def __call__(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        try:
            response = await self.get_response(request)
        except errors.JsonRpcError as e:
            logging.warning('Unprocessed errors.JsonRpcError', exc_info=True)
            response = protocol.JsonRpcResponse(
                msg_id=request.msg_id,
                jsonrpc=request.jsonrpc,
                error=e,
            )
        except Exception as e:
            logger.exception(e)
            response = protocol.JsonRpcResponse(
                msg_id=request.msg_id,
                jsonrpc=request.jsonrpc,
                error=errors.InternalError().with_traceback(),
            )

        return response


class ExtraArgsMiddleware(BaseJsonRpcMiddleware):
    async def __call__(self, request: protocol.JsonRpcRequest) -> protocol.JsonRpcResponse:
        request.extra_args['rpc_request'] = request
        return await self.get_response(request)


DEFAULT_MIDDLEWARES = (
    ExceptionMiddleware,
    ExtraArgsMiddleware,
)
