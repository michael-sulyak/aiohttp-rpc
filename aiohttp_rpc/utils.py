import json
import typing
from functools import partial
from traceback import format_exception_only

from . import constants, errors


__all__ = (
    'convert_params_to_args_and_kwargs',
    'parse_args_and_kwargs',
    'get_exc_message',
    'json_serialize',
)


def convert_params_to_args_and_kwargs(params: typing.Any) -> typing.Tuple[list, dict]:
    if params is constants.NOTHING:
        return [], {}

    if isinstance(params, constants.JSON_PRIMITIVE_TYPES):
        return [params], {}

    if isinstance(params, list):
        return params, {}

    if isinstance(params, dict):
        return [], params

    raise errors.InvalidParams('Params have unsupported data types.')


def parse_args_and_kwargs(args: typing.Any, kwargs: typing.Any) -> typing.Tuple:
    has_args = bool(args and args is not constants.NOTHING)
    has_kwargs = bool(kwargs and kwargs is not constants.NOTHING)

    if not has_args and not has_kwargs:
        return constants.NOTHING, [], {}

    if not (has_args ^ has_kwargs):
        raise errors.InvalidParams('Need use args or kwargs.')

    if has_args:
        args = list(args)

        if len(args) == 1 and isinstance(args[0], constants.JSON_PRIMITIVE_TYPES):
            return args[0], args, {}

        return args, args, {}

    kwargs = dict(kwargs)
    return kwargs, [], kwargs


def get_exc_message(exp: Exception) -> str:
    return ''.join(format_exception_only(exp.__class__, exp)).strip()


def validate_jsonrpc(jsonrpc: typing.Any) -> None:
    if jsonrpc != constants.VERSION_2_0:
        raise errors.InvalidRequest(f'Only version "{constants.VERSION_2_0}" is supported.')


json_serialize = partial(json.dumps, default=lambda x: repr(x))
