import abc
import asyncio
import inspect
import typing

from .. import errors


__all__ = (
    'BaseJSONRPCMethod',
    'JSONRPCMethod',
)


class BaseJSONRPCMethod(abc.ABC):
    name: str

    @abc.abstractmethod
    async def __call__(self,
                       args: typing.Sequence,
                       kwargs: typing.Mapping,
                       extra_kwargs: typing.Optional[typing.Mapping] = None) -> typing.Any:
        pass

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'


class JSONRPCMethod(BaseJSONRPCMethod):
    is_coroutine: bool
    is_class: bool
    _pass_extra_kwargs: bool
    _prepare_result: typing.Optional[typing.Callable]
    _signature: inspect.Signature

    def __init__(self,
                 func: typing.Callable, *,
                 name: typing.Optional[str] = None,
                 pass_extra_kwargs: bool = False,
                 prepare_result: typing.Optional[typing.Callable] = None) -> None:
        assert callable(func)

        self.func = func
        self.name = func.__name__ if name is None else name

        self._pass_extra_kwargs = pass_extra_kwargs
        self._prepare_result = prepare_result

        self._inspect_func()

    async def __call__(self,
                       args: typing.Sequence,
                       kwargs: typing.Mapping,
                       extra_kwargs: typing.Optional[typing.Mapping] = None) -> typing.Any:
        if self._pass_extra_kwargs and extra_kwargs:
            kwargs = {**kwargs, **extra_kwargs}

        self._check_func_signature(args, kwargs)

        if self.is_coroutine:
            result = await self.func(*args, **kwargs)
        else:
            result = self.func(*args, **kwargs)

        if self._prepare_result is not None:
            maybe_coro = self._prepare_result(result)
            result = await maybe_coro if inspect.isawaitable(maybe_coro) else maybe_coro

        return result

    def _inspect_func(self) -> None:
        self.is_class = inspect.isclass(self.func)
        self.is_coroutine = asyncio.iscoroutinefunction(self.func)

        if self.is_class:
            self._signature = inspect.signature(self.func.__init__)
        else:
            self._signature = inspect.signature(self.func)

    def _check_func_signature(self, args: typing.Sequence, kwargs: typing.Mapping) -> None:
        try:
            if self.is_class:
                self._signature.bind(None, *args, **kwargs)  # type: ignore
            else:
                self._signature.bind(*args, **kwargs)
        except TypeError as e:
            raise errors.InvalidParams() from e
