import asyncio
import inspect
import logging
import typing
from dataclasses import dataclass

from aiohttp import ClientResponse, web

from . import constants
from . import errors
from . import utils


class JsonRpcRequest:
    msg_id: typing.Any
    method: str
    params: typing.Any
    args: list
    kwargs: dict
    jsonrpc: str
    extra_args: dict

    def __init__(self, *,
                 msg_id: typing.Any,
                 method: str,
                 jsonrpc: str = constants.VERSION_2_0,
                 params: typing.Any = constants.NOTHING,
                 args: typing.Any = None,
                 kwargs: typing.Any = None,
                 http_request: typing.Optional[web.Request] = None) -> None:
        self.msg_id = msg_id
        self.method = method
        self.jsonrpc = jsonrpc
        self.http_request = http_request
        self.extra_args = {'rpc_request': self}

        if self.jsonrpc != constants.VERSION_2_0:
            raise errors.InvalidRequest(f'Only version {constants.VERSION_2_0} is supported.')

        if params is constants.NOTHING:
            self.params, self.args, self.kwargs = utils.parse_args_and_kwargs(args, kwargs)
        else:
            if args is not None or kwargs is not None:
                raise errors.InvalidParams('Need use params or args with kwargs.')

            self.params = params
            self.args, self.kwargs = utils.convert_params_to_args_and_kwargs(params)

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> 'JsonRpcRequest':
        if 'method' not in data:
            raise errors.MethodNotFound('Method not in data.')

        return cls(
            msg_id=data.get('id'),
            method=data['method'],
            params=data.get('params', constants.NOTHING),
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            **kwargs,
        )

    def to_dict(self) -> dict:
        data = {
            'id': self.msg_id,
            'method': self.method,
            'jsonrpc': self.jsonrpc,
        }

        if self.params is not constants.NOTHING:
            data['params'] = self.params

        return data


@dataclass
class JsonRpcResponse:
    jsonrpc: str = constants.VERSION_2_0
    msg_id: typing.Any = None
    result: typing.Any = None
    error: typing.Optional[errors.JsonRpcError] = None
    http_response: typing.Optional[ClientResponse] = None

    @classmethod
    def from_dict(cls, data: dict, *, error_map: typing.Optional[dict] = None, **kwargs) -> 'JsonRpcResponse':
        if 'id' not in data:
            raise errors.ParseError('"id" not found in data.', data={'data': data})

        if 'result' not in data and 'error' not in data:
            raise errors.ParseError('"result" or "error" not found in data.', data={'data': data})

        rpc_response = cls(
            msg_id=data['id'],
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            result=data.get('result'),
            **kwargs,
        )

        if 'error' in data:
            if error_map:
                exception_class = error_map.get(data['error']['code'], errors.JsonRpcError)
            else:
                exception_class = errors.JsonRpcError

            rpc_response.error = exception_class(
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
    separator: str = '__'
    prefix: str
    name: str
    func: typing.Callable
    add_extra_args: bool
    is_coroutine: bool
    supported_args: list
    supported_kwargs: list

    def __init__(self,
                 prefix: str,
                 func: typing.Callable, *,
                 custom_name: typing.Optional[str] = None,
                 add_extra_args: bool = True) -> None:
        assert callable(func)

        self.prefix = prefix
        self.func = func
        self.add_extra_args = add_extra_args

        if custom_name:
            self.name = custom_name
        else:
            self.name = func.__name__

        if prefix:
            self.name = f'{prefix}{self.separator}{self.name}'

        argspec = inspect.getfullargspec(func)

        if inspect.ismethod(func):
            self.supported_args = argspec.args[1:]
        else:
            self.supported_args = argspec.args

        self.supported_kwargs = argspec.kwonlyargs
        self.is_coroutine = asyncio.iscoroutinefunction(self.func)

    async def __call__(self, args: list, kwargs: dict, extra_args: typing.Optional[dict] = None) -> typing.Any:
        if self.add_extra_args and extra_args:
            args, kwargs = self._add_extra_args_in_args_and_kwargs(args, kwargs, extra_args)

        try:
            inspect.signature(self.func).bind(*args, **kwargs)
        except TypeError as e:
            raise errors.InvalidParams(utils.exc_message(e)) from e

        try:
            if self.is_coroutine:
                return await self.func(*args, **kwargs)
            else:
                return self.func(*args, **kwargs)
        except errors.JsonRpcError:
            raise
        except Exception as e:
            logging.exception(e)
            raise errors.InternalError(utils.exc_message(e)).with_traceback() from e

    def _add_extra_args_in_args_and_kwargs(self,
                                           args: list,
                                           kwargs: dict,
                                           extra_args: typing.Optional[dict] = None) -> typing.Tuple[list, dict]:
        extra_args_ = set(extra_args.keys())
        args_ = []

        for supported_arg in self.supported_args:
            if supported_arg not in extra_args_:
                break

            args_.append(extra_args[supported_arg])
            extra_args_.remove(supported_arg)

        if args_:
            args = [*args_, *args]

        if not extra_args_:
            return args, kwargs

        kwargs_ = {}

        for extra_arg in extra_args_:
            if extra_arg in self.supported_kwargs and extra_arg not in kwargs:
                kwargs_[extra_arg] = extra_args[extra_arg]

        if kwargs_:
            kwargs = {**kwargs, **kwargs_}

        return args, kwargs
