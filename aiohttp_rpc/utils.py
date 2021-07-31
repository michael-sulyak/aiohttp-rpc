import json
import typing
import uuid
from functools import partial
from traceback import format_exception_only

from . import constants, errors


__all__ = (
    'convert_params_to_args_and_kwargs',
    'parse_args_and_kwargs',
    'get_exc_message',
    'json_serialize',
)


def convert_params_to_args_and_kwargs(params: typing.Any) -> typing.Tuple[typing.Sequence, typing.Mapping]:
    if params is constants.NOTHING:
        return (), {}

    if isinstance(params, constants.JSON_PRIMITIVE_TYPES):
        return (params,), {}

    if isinstance(params, typing.Sequence):
        return params, {}

    if isinstance(params, typing.Mapping):
        return (), params

    raise errors.InvalidParams('Params have unsupported data types.')


def parse_args_and_kwargs(args: typing.Optional[typing.Sequence],
                          kwargs: typing.Optional[typing.Mapping],
                          ) -> typing.Tuple[typing.Any, typing.Sequence, typing.Mapping]:
    has_args = bool(args)
    has_kwargs = bool(kwargs)

    if not has_args and not has_kwargs:
        return constants.NOTHING, (), {}  # type: ignore

    if not (has_args ^ has_kwargs):
        raise errors.InvalidParams('Need use args or kwargs.')

    if has_args:
        if len(args) == 1 and isinstance(args[0], constants.JSON_PRIMITIVE_TYPES):  # type: ignore
            return args[0], args, {}  # type: ignore

        return args, args, {}  # type: ignore

    return kwargs, (), kwargs  # type: ignore


def get_random_id() -> str:
    return str(uuid.uuid4())


def get_exc_message(exp: BaseException) -> str:
    return ''.join(format_exception_only(exp.__class__, exp)).strip()


def validate_jsonrpc(jsonrpc: typing.Any) -> None:
    if jsonrpc != constants.VERSION_2_0:
        raise errors.InvalidRequest(f'Only version "{constants.VERSION_2_0}" is supported.')


json_serialize = partial(json.dumps, default=lambda x: repr(x))
