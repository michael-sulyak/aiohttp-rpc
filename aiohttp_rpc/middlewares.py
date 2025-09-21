import logging
import typing

from aiohttp import web

from . import client, errors, protocol


__all__ = (
    'exception_middleware',
    'inject_request_middleware',
    'logging_middleware',
    'inject_ws_client_middleware',
    'check_origins',
    'DEFAULT_MIDDLEWARES',
)

logger = logging.getLogger(__name__)


async def inject_request_middleware(request: protocol.JSONRPCRequest,
                                    handler: typing.Callable) -> protocol.JSONRPCResponse:
    request.extra_kwargs['rpc_request'] = request
    return await handler(request)


async def exception_middleware(request: protocol.JSONRPCRequest, handler: typing.Callable) -> protocol.JSONRPCResponse:
    try:
        response = await handler(request)
    except errors.JSONRPCError as e:
        logger.warning(
            'Unprocessed JSONRPCError for method="%s" id="%s"',
            request.method_name,
            request.id,
            exc_info=True,
        )
        response = protocol.JSONRPCResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            error=e,
        )
    except Exception as e:
        logger.exception(
            'Unhandled exception for method="%s" id="%s": %s',
            request.method_name,
            request.id,
            e,
        )
        response = protocol.JSONRPCResponse(
            id=request.id,
            jsonrpc=request.jsonrpc,
            error=errors.InternalError(),
        )

    return response


async def logging_middleware(request: protocol.JSONRPCRequest, handler: typing.Callable) -> protocol.JSONRPCResponse:
    raw_request = request.dump()

    logger.info(
        'JSON RPC Request id="%s" method="%s" params="%s"',
        raw_request.get('id', ''),
        raw_request['method'],
        raw_request.get('params', ''),
        extra={'request': raw_request},
    )

    response = await handler(request)

    raw_response = response.dump()

    logger.info(
        'JSON RPC Response id="%s" method="%s" params="%s" result="%s" error="%s"',
        raw_request.get('id', ''),
        raw_request['method'],
        raw_request.get('params', ''),
        raw_response.get('result', ''),
        raw_response.get('error', ''),
        extra={'request': raw_request, 'response': raw_response},
    )

    return response


async def inject_ws_client_middleware(request: protocol.JSONRPCRequest,
                                      handler: typing.Callable) -> protocol.JSONRPCResponse:
    ws_connect = request.context['ws_connect']
    request.context['ws_rpc_client'] = client.WSJSONRPCClient(ws_connect=ws_connect)
    request.extra_kwargs['ws_rpc_client'] = request.context['ws_rpc_client']
    return await handler(request)


def check_origins(allowed_origins: typing.Iterable[str]) -> typing.Callable:
    allowed_origins = set(allowed_origins)

    async def _check_origins(request: protocol.JSONRPCRequest,
                             handler: typing.Callable) -> protocol.JSONRPCResponse:
        http_request = request.context['http_request']
        origin = http_request.headers.get('Origin')

        if origin not in allowed_origins:
            raise web.HTTPForbidden(reason='Origin not allowed.')

        return await handler(request)

    return _check_origins


DEFAULT_MIDDLEWARES = (
    exception_middleware,
    inject_request_middleware,
)
