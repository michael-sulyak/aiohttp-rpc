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
    doc: typing.Optional[str] = None
    supported_args: typing.Tuple[str, ...] = ()
    supported_kwargs: typing.Tuple[str, ...] = ()

    @abc.abstractmethod
    async def __call__(self,
                       args: typing.Sequence,
                       kwargs: typing.Mapping,
                       extra_args: typing.Optional[typing.Mapping] = None) -> typing.Any:
        pass

    def __repr__(self) -> str:
        args = ', '.join(self.supported_args)

        if self.supported_args and self.supported_kwargs:
            args += ', *, '

        if self.supported_kwargs:
            args += ', '.join(self.supported_kwargs)

        return f'JsonRpcMethod({self.name}({args}))'


class JsonRpcMethod(BaseJsonRpcMethod):
    is_coroutine: bool
    is_class: bool
    _add_extra_args: bool
    _prepare_result: typing.Optional[typing.Callable]

    def __init__(self,
                 func: typing.Callable, *,
                 name: typing.Optional[str] = None,
                 add_extra_args: bool = True,
                 prepare_result: typing.Optional[typing.Callable] = None) -> None:
        assert callable(func)

        self.func = func
        self.name = name if name is not None else func.__name__
        self.doc = self.func.__doc__

        self._add_extra_args = add_extra_args
        self._prepare_result = prepare_result

        self._inspect_func()

    async def __call__(self,
                       args: typing.Sequence,
                       kwargs: typing.Mapping,
                       extra_args: typing.Optional[typing.Mapping] = None) -> typing.Any:
        if self._add_extra_args and extra_args:
            args, kwargs = self._add_extra_args_in_args_and_kwargs(args, kwargs, extra_args)

        self._check_func_signature(args, kwargs)

        if self.is_coroutine:
            result = await self.func(*args, **kwargs)
        else:
            result = self.func(*args, **kwargs)

        if self._prepare_result is not None:
            result = self._prepare_result(result)

        return result

    def _inspect_func(self) -> None:
        self.is_class = inspect.isclass(self.func)
        func = self.func.__init__ if self.is_class else self._unwrap_func(self.func)  # type: ignore

        argspec = inspect.getfullargspec(func)

        if self.is_class or inspect.ismethod(func):
            self.supported_args = tuple(argspec.args[1:])
        else:
            self.supported_args = tuple(argspec.args)

        self.supported_kwargs = tuple(argspec.kwonlyargs)
        self.is_coroutine = asyncio.iscoroutinefunction(func)

    @staticmethod
    def _unwrap_func(func: typing.Callable) -> typing.Callable:
        i = 0

        while hasattr(func, '__wrapped__'):
            func = func.__wrapped__  # type: ignore
            i += 1

            if i > 1_000:
                raise errors.InternalError('The method has too many wrappers.')

        return func

    def _add_extra_args_in_args_and_kwargs(self,
                                           args: typing.Sequence,
                                           kwargs: typing.Mapping,
                                           extra_args: typing.Mapping) -> typing.Tuple[typing.Sequence, typing.Mapping]:
        if not extra_args:
            return args, kwargs

        new_args = self._add_extra_args_in_args(args, extra_args)

        if (len(new_args) - len(args)) == len(extra_args):
            return new_args, kwargs

        new_kwargs = self._add_extra_kwargs_in_args(kwargs, extra_args)
        return new_args, new_kwargs

    def _add_extra_args_in_args(self, args: typing.Sequence, extra_args: typing.Mapping) -> typing.Sequence:
        if self.supported_args:
            new_args = []

            for supported_arg in self.supported_args:
                if supported_arg not in extra_args:
                    # We add extra args only in the begin.
                    break

                new_args.append(extra_args[supported_arg])

            if new_args:
                new_args.extend(args)
                args = new_args

        return args

    def _add_extra_kwargs_in_args(self, kwargs: typing.Mapping, extra_args: typing.Mapping) -> typing.Mapping:
        if extra_args:
            new_kwargs = {}

            for extra_arg, value in extra_args.items():
                if extra_arg in self.supported_kwargs:
                    new_kwargs[extra_arg] = value

            if new_kwargs:
                new_kwargs.update(kwargs)
                kwargs = new_kwargs

        return kwargs

    def _check_func_signature(self, args: typing.Sequence, kwargs: typing.Mapping) -> None:
        try:
            if self.is_class:
                inspect.signature(self.func.__init__).bind(None, *args, **kwargs)  # type: ignore
            else:
                inspect.signature(self.func).bind(*args, **kwargs)
        except TypeError as e:
            raise errors.InvalidParams(utils.get_exc_message(e)) from e
