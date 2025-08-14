import typing

from .protocol import JSONRPCMethod
from .server import JSONRPCServer, rpc_server as default_rpc_server


__all__ = (
    'rpc_method',
)


def rpc_method(name: typing.Optional[str] = None, *,
               rpc_server: JSONRPCServer = default_rpc_server,
               pass_extra_kwargs: bool = True,
               prepare_result: typing.Optional[typing.Callable] = None) -> typing.Callable:
    def _decorator(func: typing.Callable) -> typing.Callable:
        rpc_server.add_method(JSONRPCMethod(
            func=func,
            name=name,
            pass_extra_kwargs=pass_extra_kwargs,
            prepare_result=prepare_result,
        ))
        return func

    return _decorator
