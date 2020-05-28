import asyncio
import inspect
import typing

from .. import errors, utils


__all__ = (
    'JsonRpcMethod',
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
