import asyncio
import inspect
import typing
from dataclasses import dataclass

from aiohttp import web

from . import exceptions


class DEFAULT:
    pass


class JsonRpcRequest:
    msg_id: typing.Any
    method: str
    params: typing.Any
    args: list
    kwargs: dict
    jsonrpc: str

    def __init__(self, *,
                 msg_id: typing.Any,
                 method: str,
                 jsonrpc: str = '2.0',
                 params: typing.Any = DEFAULT,
                 args: typing.Any = DEFAULT,
                 kwargs: typing.Any = DEFAULT,
                 http_request: typing.Optional[web.Request] = None) -> None:
        self.msg_id = msg_id
        self.method = method
        self.jsonrpc = jsonrpc
        self.http_request = http_request

        if params is not DEFAULT:
            if args is not DEFAULT or kwargs is not DEFAULT:
                raise exceptions.InvalidParams('Need use params or args with kwargs.')

            self._parse_params(params)
        else:
            self._parse_args_and_kwargs(args, kwargs)

    def _parse_params(self, params: typing.Any) -> None:
        self.params = params

        if isinstance(self.params, (str, int, float, bool,)) or self.params is None:
            self.args = [self.params]
            self.kwargs = {}
        elif isinstance(self.params, list):
            self.args = self.params
            self.kwargs = {}
        elif isinstance(self.params, dict):
            self.args = []
            self.kwargs = self.params
        else:
            self.args = [self.params]
            self.kwargs = {}

    def _parse_args_and_kwargs(self, args: typing.Any, kwargs: typing.Any) -> None:
        has_args = bool(args is not DEFAULT and args)
        has_kwargs = bool(kwargs is not DEFAULT and kwargs)

        if not has_args and not has_kwargs:
            self.params = DEFAULT
            self.args = []
            self.kwargs = {}
            return

        if not (has_args ^ has_kwargs):
            raise exceptions.InvalidParams('Need use args or kwargs.')

        if has_args:
            args = list(args)
            self.params = args
            self.args = args
            self.kwargs = {}
        elif has_kwargs:
            kwargs = dict(kwargs)
            self.params = kwargs
            self.args = []
            self.kwargs = kwargs

    def to_dict(self) -> dict:
        data = {
            'msg_id': self.msg_id,
            'method': self.method,
            'jsonrpc': self.jsonrpc,
        }

        if self.params is not DEFAULT:
            data['params'] = self.params

        return data


@dataclass
class JsonRpcResponse:
    jsonrpc: str = '2.0'
    msg_id: typing.Any = None
    result: typing.Any = None
    error: exceptions.JsonRpcError = None

    @classmethod
    def from_dict(cls, data: dict) -> 'JsonRpcResponse':
        if 'id' not in data:
            raise exceptions.ParseError(data=data)

        if 'result' not in data and 'error' not in data:
            raise exceptions.ParseError(data=data)

        rpc_response = cls(
            msg_id=data['id'],
            jsonrpc=data.get('jsonrpc', '2.0'),
            result=data.get('result'),
        )

        if 'error' in data:
            rpc_response.error = exceptions.JsonRpcError(
                message=data['error']['message'],
                data=data['error'].get('data'),
                code=data['error']['code'],
            )

        return rpc_response

    def to_dict(self) -> dict:
        data = {'id': self.msg_id, 'jsonrpc': self.jsonrpc}

        if self.error:
            data['error'] = {'code': self.error.code, 'message': self.error.message}

            if self.error.data is not None:
                data['error']['data'] = self.error.data
        else:
            data['result'] = self.result

        return data


class JsonRpcMethod:
    prefix: str
    name: str
    method: typing.Callable
    supported_args: list
    supported_kwargs: list
    all_supported_args: set
    without_extra_args: bool
    is_coroutine: bool

    def __init__(self,
                 prefix: str,
                 method: typing.Callable,
                 *,
                 custom_name: typing.Optional[str] = None,
                 without_extra_args: bool = False) -> None:
        self.prefix = prefix
        self.method = method
        self.without_extra_args = without_extra_args

        if custom_name is None:
            self.name = method.__name__
        else:
            self.name = custom_name

        if prefix:
            self.name = f'{prefix}__{self.name}'

        argspec = inspect.getfullargspec(method)

        if inspect.ismethod(method):
            self.supported_args = argspec.args[1:]
        else:
            self.supported_args = argspec.args

        self.supported_kwargs = argspec.kwonlyargs
        self.all_supported_args = set(self.supported_args) | set(self.supported_kwargs)
        self.is_coroutine = asyncio.iscoroutinefunction(self.method)

    async def __call__(self, args: list, kwargs: dict, extra_kwargs: typing.Optional[dict] = None):
        extra_kwargs_ = {}

        if not self.without_extra_args and extra_kwargs is not None:
            for key, value in extra_kwargs.items():
                if key in self.all_supported_args:
                    extra_kwargs_[key] = value

        if self.is_coroutine:
            return await self.method(*args, **kwargs, **extra_kwargs_)
        else:
            return self.method(*args, **kwargs, **extra_kwargs_)
