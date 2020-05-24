import typing

from .protocol import JsonRpcMethod
from .rpc import default_rpc_manager


def rpc_method(prefix: str = '', *,
               custom_name: typing.Optional[str] = None,
               without_extra_args: bool = False) -> typing.Callable:
    def _decorator(func: typing.Callable) -> typing.Callable:
        method = JsonRpcMethod(
            prefix=prefix,
            method=func,
            custom_name=custom_name,
            without_extra_args=without_extra_args,
        )
        default_rpc_manager.add_method(method)
        return func

    return _decorator
