import json
import typing
import uuid
from functools import partial

from . import constants, errors


if typing.TYPE_CHECKING:
    from . import protocol  # NOQA

__all__ = (
    'convert_params_to_args_and_kwargs',
    'parse_args_and_kwargs',
    'json_serialize',
    'collect_batch_result',
)


def convert_params_to_args_and_kwargs(params: typing.Any) -> typing.Tuple[typing.Sequence, typing.Mapping]:
    if params is constants.NOTHING:
        return (), {}

    if isinstance(params, constants.JSON_PRIMITIVE_TYPES):
        raise errors.InvalidRequest(f'Params must be an array or object per JSON-RPC 2.0. {params}')

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

    if has_args and has_kwargs:
        raise errors.InvalidParams(data={'details': 'Need use args or kwargs.'})

    if has_args:
        return args, args, {}  # type: ignore

    return kwargs, (), kwargs  # type: ignore


def get_random_id() -> str:
    return str(uuid.uuid4())


def validate_jsonrpc(jsonrpc: typing.Any) -> None:
    if jsonrpc is None:
        raise errors.InvalidRequest(f'The "jsonrpc" field is required and must be "{constants.VERSION_2_0}".')

    if jsonrpc != constants.VERSION_2_0:
        raise errors.InvalidRequest(f'Only version "{constants.VERSION_2_0}" is supported.')


def collect_batch_result(batch_request: 'protocol.JSONRPCBatchRequest',
                         batch_response: 'protocol.JSONRPCBatchResponse') -> typing.Tuple[typing.Any, ...]:
    from . import protocol

    unlinked_results = protocol.JSONRPCUnlinkedResults()
    responses_map: typing.Dict[typing.Any, typing.Any] = {}

    for response in batch_response.responses:
        if response.error is None:
            value = response.result
        else:
            value = response.error

        if response.id is None:
            unlinked_results.add(value)
            continue

        if response.id in responses_map:
            if isinstance(responses_map[response.id], protocol.JSONRPCDuplicatedResults):
                responses_map[response.id].add(value)
            else:
                responses_map[response.id] = protocol.JSONRPCDuplicatedResults([
                    responses_map[response.id],
                    value,
                ])
        else:
            responses_map[response.id] = value

    return tuple(
        unlinked_results or None
        if request.is_notification
        else responses_map.get(request.id, unlinked_results or None)
        for request in batch_request.requests
    )


json_serialize = partial(json.dumps, default=lambda x: f'<non-serializable {type(x).__name__}>')
json_deserialize = json.loads
