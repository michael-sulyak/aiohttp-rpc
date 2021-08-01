import typing

from .protocol import JsonRpcMethod
from .server import JsonRpcServer, rpc_server as default_rpc_server


__all__ = (
    'rpc_method',
)


def rpc_method(*,
               rpc_server: JsonRpcServer = default_rpc_server,
               prefix: typing.Optional[str] = None,
               custom_name: typing.Optional[str] = None,
               add_extra_args: bool = True) -> typing.Callable:
    def _decorator(func: typing.Callable) -> typing.Callable:
        rpc_server.add_method(JsonRpcMethod(
            func=func,
            prefix=prefix,
            custom_name=custom_name,
            add_extra_args=add_extra_args,
        ))
        return func

    return _decorator
