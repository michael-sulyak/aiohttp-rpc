import typing
from functools import lru_cache

from .. import protocol, utils


if typing.TYPE_CHECKING:
    from . import base  # NOQA


class JSONRPCClientMethod:
    _client: 'base.BaseJSONRPCClient'
    _method_name: str

    def __init__(self, client: 'base.BaseJSONRPCClient', *, method_name: str) -> None:
        self._client = client
        self._method_name = method_name

    async def __call__(self, *args, **kwargs) -> typing.Any:
        return await self._client.call(self._method_name, *args, **kwargs)

    async def notify(self, *args, **kwargs) -> None:
        await self._client.notify(self._method_name, *args, **kwargs)

    def request(self, *args, **kwargs) -> protocol.JSONRPCRequest:
        return protocol.JSONRPCRequest(
            id=utils.get_random_id(),
            method_name=self._method_name,
            args=args,
            kwargs=kwargs,
        )

    def notification(self, *args, **kwargs) -> protocol.JSONRPCRequest:
        return protocol.JSONRPCRequest(
            method_name=self._method_name,
            args=args,
            kwargs=kwargs,
        )


class JSONRPCClientMethods:
    __client: 'base.BaseJSONRPCClient'

    def __init__(self, client: 'base.BaseJSONRPCClient') -> None:
        self.__client = client

    @lru_cache(maxsize=100)
    def __getattr__(self, method_name: str) -> JSONRPCClientMethod:
        return JSONRPCClientMethod(self.__client, method_name=method_name)
