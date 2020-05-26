import typing

from .protocol import JsonRpcMethod
from .server import JsonRpcServer, rpc_server as default_rpc_server


__all__ = (
    'rpc_method',
)


def rpc_method(prefix: str = '', *,
               rpc_server: JsonRpcServer = default_rpc_server,
               custom_name: typing.Optional[str] = None,
               add_extra_args: bool = True) -> typing.Callable:
    def _decorator(func: typing.Callable) -> typing.Callable:
        method = JsonRpcMethod(
            prefix=prefix,
            func=func,
            custom_name=custom_name,
            add_extra_args=add_extra_args,
        )
        rpc_server.add_method(method)
        return func

    return _decorator
