import abc
import asyncio
import inspect
import typing

from .. import errors, utils


__all__ = (
    'BaseJsonRpcMethod',
    'JsonRpcMethod',
)


class BaseJsonRpcMethod(abc.ABC):
    name: str
    func: typing.Union[typing.Callable, typing.Type]
    separator: str = '__'

    def __init__(self,
                 prefix: str,
                 func: typing.Union[typing.Callable, typing.Type], *,
                 custom_name: typing.Optional[str] = None) -> None:
        assert callable(func)

        self.func = func
        self.name = custom_name if custom_name else func.__name__

        if prefix:
            self.name = f'{prefix}{self.separator}{self.name}'

    @abc.abstractmethod
    async def __call__(self, args: list, kwargs: dict, extra_args: typing.Optional[dict] = None) -> typing.Any:
        pass


class JsonRpcMethod(BaseJsonRpcMethod):
    add_extra_args: bool
    is_coroutine: bool
    is_class: bool
    supported_args: list
    supported_kwargs: list
    prepare_result: typing.Optional[typing.Callable]

    def __init__(self,
                 prefix: str,
                 func: typing.Union[typing.Callable, typing.Type], *,
                 custom_name: typing.Optional[str] = None,
                 add_extra_args: bool = True,
                 prepare_result: typing.Optional[typing.Callable] = None) -> None:
        super().__init__(prefix, func, custom_name=custom_name)

        self.add_extra_args = add_extra_args
        self.prepare_result = prepare_result

        self._inspect_func()

    async def __call__(self, args: list, kwargs: dict, extra_args: typing.Optional[dict] = None) -> typing.Any:
        if self.add_extra_args and extra_args:
            args, kwargs = self._add_extra_args_in_args_and_kwargs(args, kwargs, extra_args)

        self._check_func_signature(args, kwargs)

        if self.is_coroutine:
            result = await self.func(*args, **kwargs)
        else:
            result = self.func(*args, **kwargs)

        if self.prepare_result:
            result = self.prepare_result(result)

        return result

    def _inspect_func(self) -> None:
        self.is_class = inspect.isclass(self.func)
        func = self.func.__init__ if self.is_class else self._unwrap_func(self.func)

        argspec = inspect.getfullargspec(func)

        if self.is_class or inspect.ismethod(func):
            self.supported_args = argspec.args[1:]
        else:
            self.supported_args = argspec.args

        self.supported_kwargs = argspec.kwonlyargs
        self.is_coroutine = asyncio.iscoroutinefunction(func)

    @staticmethod
    def _unwrap_func(func: typing.Callable) -> typing.Callable:
        i = 0

        while hasattr(func, '__wrapped__'):
            func = func.__wrapped__
            i += 1

            if i > 1_000:
                raise errors.InternalError('The method has too many wrappers.')

        return func

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

    def _check_func_signature(self, args: list, kwargs: dict) -> None:
        try:
            if self.is_class:
                inspect.signature(self.func.__init__).bind(None, *args, **kwargs)
            else:
                inspect.signature(self.func).bind(*args, **kwargs)
        except TypeError as e:
            raise errors.InvalidParams(utils.get_exc_message(e)) from e
