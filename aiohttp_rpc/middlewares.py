import logging
import typing

from . import errors, protocol, client


__all__ = (
    'exception_middleware',
    'extra_args_middleware',
    'logging_middleware',
    'ws_client_for_server_response',
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
        logger.warning('Unprocessed errors.JsonRpcError', exc_info=True)
        response = protocol.JsonRpcResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            error=e,
        )
    except Exception as e:
        logger.exception(e)
        response = protocol.JsonRpcResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            error=errors.InternalError().with_traceback(),
        )

    return response


async def logging_middleware(request: protocol.JsonRpcRequest, handler: typing.Callable) -> protocol.JsonRpcResponse:
    raw_request = request.to_dict()

    logger.info(
        'RpcRequest id="%s" method="%s" params="%s"',
        raw_request.get('id', ''),
        raw_request['method'],
        raw_request.get('params', ''),
        extra={'request': raw_request},
    )

    response = await handler(request)

    raw_response = request.to_dict()

    logger.info(
        'RpcResponse id="%s" method="%s" params="%s" result="%s" error="%s"',
        raw_request.get('id', ''),
        raw_request['method'],
        raw_request.get('params', ''),
        raw_response.get('result', ''),
        raw_response.get('error', ''),
        extra={'request': raw_response, 'response': raw_response},
    )

    return response


async def ws_client_for_server_response(request: protocol.JsonRpcRequest,
                                        handler: typing.Callable) -> protocol.JsonRpcResponse:
    ws_connect = request.context['ws_connect']
    request.context['ws_client'] = client.WsJsonRpcClient(ws_connect=ws_connect)
    request.extra_args['rpc_ws_client'] = request.context['ws_client']
    return await handler(request)


DEFAULT_MIDDLEWARES = (
    exception_middleware,
    extra_args_middleware,
)
