import typing

from .protocol import JsonRpcMethod
from .server import JsonRpcServer, default_rpc_server


def rpc_method(prefix: str = '', *,
               rpc_manager: JsonRpcServer = default_rpc_server,
               custom_name: typing.Optional[str] = None,
               without_extra_args: bool = False) -> typing.Callable:
    def _decorator(func: typing.Callable) -> typing.Callable:
        method = JsonRpcMethod(
            prefix=prefix,
            method=func,
            custom_name=custom_name,
            without_extra_args=without_extra_args,
        )
        rpc_manager.add_method(method)
        return func

    return _decorator
