import asyncio
import inspect
import logging
import typing
from dataclasses import dataclass

from aiohttp import web

from . import constants
from . import exceptions
from . import utils


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
                 params: typing.Any = constants.NOTHING,
                 args: typing.Any = None,
                 kwargs: typing.Any = None,
                 http_request: typing.Optional[web.Request] = None) -> None:
        self.msg_id = msg_id
        self.method = method
        self.jsonrpc = jsonrpc
        self.http_request = http_request

        if params is not constants.NOTHING:
            if args is not None or kwargs is not None:
                raise exceptions.InvalidParams('Need use params or args with kwargs.')

            self.params = params
            self.args, self.kwargs = utils.convert_params_to_args_and_kwargs(params)
        else:
            self.params, self.args, self.kwargs = utils.parse_args_and_kwargs(args, kwargs)

    def to_dict(self) -> dict:
        data = {
            'msg_id': self.msg_id,
            'method': self.method,
            'jsonrpc': self.jsonrpc,
        }

        if self.params is not constants.NOTHING:
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
    required_args: set
    required_kwargs: set
    without_extra_args: bool
    is_coroutine: bool
    has_varargs: bool
    has_varkw: bool

    def __init__(self,
                 prefix: str,
                 method: typing.Callable, *,
                 custom_name: typing.Optional[str] = None,
                 without_extra_args: bool = False) -> None:
        assert callable(method)

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

        self.has_varargs = argspec.varargs is not None
        self.has_varkw = argspec.varkw is not None
        self.supported_kwargs = argspec.kwonlyargs
        self.all_supported_args = set(self.supported_args) | set(self.supported_kwargs)
        self.required_args = set(self.supported_args[len(argspec.defaults or []):])
        self.required_kwargs = (
            set(self.supported_kwargs) - set(argspec.kwonlydefaults.keys() if argspec.kwonlydefaults else [])
        )
        self.is_coroutine = asyncio.iscoroutinefunction(self.method)

    async def __call__(self, args: list, kwargs: dict, extra_kwargs: typing.Optional[dict] = None) -> typing.Any:
        extra_kwargs_ = {}

        if not self.without_extra_args and extra_kwargs is not None:
            for key, value in extra_kwargs.items():
                if key in self.all_supported_args:
                    extra_kwargs_[key] = value

        kwargs_keys = set(kwargs.keys())

        if self.required_args:
            required_args = set(self.supported_args) - kwargs_keys
        else:
            required_args = self.required_args

        if required_args and len(self.required_kwargs) > len(args):
            raise exceptions.InvalidParams

        if self.required_kwargs and len(self.required_kwargs - kwargs_keys) > 0:
            raise exceptions.InvalidParams

        if not self.has_varkw and len(kwargs_keys - self.all_supported_args) > 0:
            raise exceptions.InvalidParams

        if not self.has_varargs and len(self.supported_args) < len(args):
            raise exceptions.InvalidParams

        try:
            if self.is_coroutine:
                return await self.method(*args, **kwargs, **extra_kwargs_)
            else:
                return self.method(*args, **kwargs, **extra_kwargs_)
        except exceptions.JsonRpcError:
            raise
        except Exception as e:
            logging.exception(e)
            raise exceptions.JsonRpcError from e
