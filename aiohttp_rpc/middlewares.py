import logging
import typing

from . import errors, protocol


__all__ = (
    'exception_middleware',
    'extra_args_middleware',
    'DEFAULT_MIDDLEWARES',
)

logger = logging.getLogger(__name__)


async def extra_args_middleware(request: protocol.JsonRpcRequest, handler: typing.Callable) -> protocol.JsonRpcResponse:
    request.extra_args['rpc_request'] = request
    return await handler(request)


async def exception_middleware(request: protocol.JsonRpcRequest, handler: typing.Callable) -> protocol.JsonRpcResponse:
    try:
        response = await handler(request)
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


DEFAULT_MIDDLEWARES = (
    exception_middleware,
    extra_args_middleware,
)
