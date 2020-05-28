import asyncio
import inspect
import typing
from dataclasses import dataclass, field

from . import constants
from . import errors
from . import utils


__all__ = (
    'JsonRpcRequest',
    'JsonRpcResponse',
    'JsonRpcMethod',
)


class JsonRpcRequest:
    msg_id: typing.Any
    method: str
    jsonrpc: str
    extra_args: dict
    context: dict
    _params: typing.Any
    _args: list
    _kwargs: dict

    def __init__(self, *,
                 msg_id: typing.Any = constants.NOTHING,
                 method: str,
                 jsonrpc: typing.Any = constants.VERSION_2_0,
                 params: typing.Any = constants.NOTHING,
                 args: typing.Any = None,
                 kwargs: typing.Any = None,
                 context: typing.Optional[dict] = None) -> None:
        utils.validate_jsonrpc(jsonrpc)

        self.msg_id = msg_id
        self.method = method
        self.jsonrpc = jsonrpc
        self.extra_args = {}
        self.context = {} if context is None else context

        if params is constants.NOTHING:
            self.args_and_kwargs = args, kwargs
        elif not args and not kwargs:
            self.params = params
        else:
            raise errors.InvalidParams('Need use params or args with kwargs.')

    @property
    def params(self) -> typing.Any:
        return self._params

    @params.setter
    def params(self, value: typing.Any) -> None:
        self._params = value
        self._args, self._kwargs = utils.convert_params_to_args_and_kwargs(value)

    @property
    def args(self) -> list:
        return self._args

    @property
    def kwargs(self) -> dict:
        return self._kwargs

    @property
    def args_and_kwargs(self) -> typing.Tuple[list, dict]:
        return self._args, self._kwargs

    @args_and_kwargs.setter
    def args_and_kwargs(self, value: typing.Tuple[typing.Optional[list], typing.Optional[dict]]) -> None:
        self._params, self._args, self._kwargs = utils.parse_args_and_kwargs(*value)

    @property
    def is_notification(self) -> bool:
        return self.msg_id is constants.NOTHING

    @classmethod
    def from_dict(cls, data: typing.Dict[str, typing.Any], **kwargs) -> 'JsonRpcRequest':
        cls._validate_json_request(data)

        return cls(
            msg_id=data.get('id', constants.NOTHING),
            method=data['method'],
            params=data.get('params', constants.NOTHING),
            jsonrpc=data['jsonrpc'],
            **kwargs,
        )

    def to_dict(self) -> dict:
        data = {
            'method': self.method,
            'jsonrpc': self.jsonrpc,
        }

        if not self.is_notification:
            data['id'] = self.msg_id

        if self.params is not constants.NOTHING:
            data['params'] = self.params

        return data

    @staticmethod
    def _validate_json_request(data: typing.Any) -> None:
        if not isinstance(data, dict):
            raise errors.InvalidRequest('A request must be of the dict type.')

        if not ({'method', 'jsonrpc'}) <= data.keys():
            raise errors.InvalidRequest('A request must contain "method" and "jsonrpc".')

        utils.validate_jsonrpc(data['jsonrpc'])


@dataclass
class JsonRpcResponse:
    jsonrpc: str = constants.VERSION_2_0
    msg_id: typing.Any = constants.NOTHING
    result: typing.Any = constants.NOTHING
    error: typing.Optional[errors.JsonRpcError] = None
    context: dict = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.msg_id is constants.NOTHING

    @classmethod
    def from_dict(cls, data: dict, *, error_map: typing.Optional[dict] = None, **kwargs) -> 'JsonRpcResponse':
        cls._validate_json_response(data)

        response = cls(
            msg_id=data.get('id', constants.NOTHING),
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            result=data.get('result'),
            **kwargs,
        )

        if 'error' in data:
            cls._add_error(response, data['error'], error_map=error_map)

        return response

    def to_dict(self) -> typing.Optional[dict]:
        if self.msg_id is constants.NOTHING:
            return None

        data = {'id': self.msg_id, 'jsonrpc': self.jsonrpc}

        if self.error is constants.NOTHING:
            data['result'] = self.result
        else:
            data['error'] = {'code': self.error.code, 'message': self.error.message}

            if self.error.data is not None:
                data['error']['data'] = self.error.data

        return data

    @staticmethod
    def _validate_json_response(data: typing.Any) -> None:
        if not isinstance(data, dict):
            raise errors.InvalidRequest

        utils.validate_jsonrpc(data.get('jsonrpc'))

        if 'result' not in data and 'error' not in data:
            raise errors.InvalidRequest('"result" or "error" not found in data.', data={'raw_response': data})

    @staticmethod
    def _add_error(response: 'JsonRpcResponse', error: typing.Any, *, error_map: typing.Optional[dict] = None) -> None:
        if not isinstance(error, dict):
            raise errors.InvalidRequest

        if not ({'code', 'message'}) <= error.keys():
            raise errors.InvalidRequest

        if error_map:
            exception_class = error_map.get(error['code'], errors.JsonRpcError)
        else:
            exception_class = errors.JsonRpcError

        response.error = exception_class(
            message=error['message'],
            data=error.get('data'),
            code=error['code'],
        )


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
        self.name = custom_name if custom_name else func.__name__

        if prefix:
            self.name = f'{prefix}{self.separator}{self.name}'

        self._inspect_func()

    async def __call__(self, args: list, kwargs: dict, extra_args: typing.Optional[dict] = None) -> typing.Any:
        if self.add_extra_args and extra_args:
            args, kwargs = self._add_extra_args_in_args_and_kwargs(args, kwargs, extra_args)

        try:
            inspect.signature(self.func).bind(*args, **kwargs)
        except TypeError as e:
            raise errors.InvalidParams(utils.get_exc_message(e)) from e

        if self.is_coroutine:
            return await self.func(*args, **kwargs)

        return self.func(*args, **kwargs)

    def _inspect_func(self) -> None:
        argspec = inspect.getfullargspec(self.func)

        if inspect.ismethod(self.func):
            self.supported_args = argspec.args[1:]
        else:
            self.supported_args = argspec.args

        self.supported_kwargs = argspec.kwonlyargs
        self.is_coroutine = asyncio.iscoroutinefunction(self.func)

    def _add_extra_args_in_args_and_kwargs(self,
                                           args: list,
                                           kwargs: dict,
                                           extra_args: dict) -> typing.Tuple[list, dict]:
        if not extra_args:
            return args, kwargs

        new_args = self._add_extra_args_in_args(args, extra_args)

        if (len(new_args) - len(args)) == len(extra_args):
            return new_args, kwargs

        new_kwargs = self._add_extra_kwargs_in_args(kwargs, extra_args)
        return new_args, new_kwargs

    def _add_extra_args_in_args(self, args: list, extra_args: dict) -> list:
        new_args = []

        for supported_arg in self.supported_args:
            if supported_arg not in extra_args:
                break

            new_args.append(extra_args[supported_arg])

        if new_args:
            args = [*new_args, *args]

        return args

    def _add_extra_kwargs_in_args(self, kwargs: dict, extra_args: dict) -> dict:
        new_kwargs = {}

        for extra_arg, value in extra_args.items():
            if extra_arg in self.supported_kwargs:
                new_kwargs[extra_arg] = value

        if new_kwargs:
            kwargs = {**kwargs, **new_kwargs}

        return kwargs
