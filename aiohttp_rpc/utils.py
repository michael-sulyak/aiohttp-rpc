import typing

from . import constants, exceptions


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
        raise exceptions.InvalidParams('Need use args or kwargs.')

    if has_args:
        args = list(args)
        params = args
        kwargs = {}
    elif has_kwargs:
        kwargs = dict(kwargs)
        params = kwargs
        args = []

    return params, args, kwargs
