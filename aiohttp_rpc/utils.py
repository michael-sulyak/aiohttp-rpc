import json
import typing
from functools import partial
from traceback import format_exception_only

from . import constants, errors


__all__ = (
    'convert_params_to_args_and_kwargs',
    'parse_args_and_kwargs',
    'exc_message',
    'json_serialize',
)


def convert_params_to_args_and_kwargs(params: typing.Any) -> typing.Tuple[list, dict]:
    if isinstance(params, (str, int, float, bool,)) or params is None:
        args = [params]
        kwargs = {}
    elif isinstance(params, list):
        args = params
        kwargs = {}
    elif isinstance(params, dict):
        args = []
        kwargs = params
    else:
        args = [params]
        kwargs = {}

    return args, kwargs


def parse_args_and_kwargs(args: typing.Any, kwargs: typing.Any) -> typing.Tuple:
    has_args = bool(args and args is not constants.NOTHING)
    has_kwargs = bool(kwargs and kwargs is not constants.NOTHING)

    if not has_args and not has_kwargs:
        params = constants.NOTHING
        args = []
        kwargs = {}
        return params, args, kwargs

    if not (has_args ^ has_kwargs):
        raise errors.InvalidParams('Need use args or kwargs.')

    if has_args:
        kwargs = {}
        args = list(args)
        params = args
    else:
        args = []
        kwargs = dict(kwargs)
        params = kwargs

    return params, args, kwargs


def exc_message(exp: Exception) -> str:
    return ''.join(format_exception_only(exp.__class__, exp)).strip()


json_serialize = partial(json.dumps, default=lambda x: repr(x))
