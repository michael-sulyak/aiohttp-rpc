import typing
from dataclasses import dataclass, field

from .. import constants, errors, typedefs, utils


__all__ = (
    'JsonRpcResponse',
    'JsonRpcBatchResponse',
    'JsonRpcUnlinkedResults',
    'JsonRpcDuplicatedResults',
)


@dataclass
class JsonRpcResponse:
    id: typing.Optional[typedefs.JsonRpcIdType] = None
    jsonrpc: str = constants.VERSION_2_0
    result: typing.Any = None
    error: typing.Optional[errors.JsonRpcError] = None
    context: typing.MutableMapping = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.id is None

    @classmethod
    def load(cls,
             data: typing.Any, *,
             error_map: typing.Optional[typing.Mapping] = None, **kwargs) -> 'JsonRpcResponse':
        cls._validate_json_response(data)

        response = cls(
            id=data.get('id'),
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            result=data.get('result'),
            **kwargs,
        )

        if 'error' in data:
            cls._add_error(response, data['error'], error_map=error_map)

        return response

    def dump(self) -> typing.Mapping[str, typing.Any]:
        data: typing.Dict[str, typing.Any] = {
            'id': self.id,
            'jsonrpc': self.jsonrpc,
        }

        if self.error is None:
            data['result'] = self.result
        else:
            data['error'] = {'code': self.error.code, 'message': self.error.message}

            if self.error.data is not None:
                data['error']['data'] = self.error.data

        return data

    @staticmethod
    def _validate_json_response(data: typing.Any) -> None:
        if not isinstance(data, typing.Mapping):
            raise errors.InvalidRequest

        utils.validate_jsonrpc(data.get('jsonrpc'))

        if 'result' not in data and 'error' not in data:
            raise errors.InvalidRequest('"result" or "error" not found in data.', data={'raw_response': data})

    @staticmethod
    def _add_error(response: 'JsonRpcResponse',
                   error: typing.Any, *,
                   error_map: typing.Optional[typing.Mapping] = None) -> None:
        if not isinstance(error, typing.Mapping):
            raise errors.InvalidRequest

        if not {'code', 'message'} <= error.keys():
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


@dataclass
class JsonRpcBatchResponse:
    responses: typing.Tuple[JsonRpcResponse, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls,
             data: typing.Any, *,
             error_map: typing.Optional[typing.Mapping] = None,
             **kwargs) -> 'JsonRpcBatchResponse':
        if not isinstance(data, typing.Sequence):
            raise errors.InvalidRequest('A batch request must be of the list type.')

        return cls(responses=tuple(
            JsonRpcResponse.load(item, error_map=error_map, **kwargs)
            for item in data
        ))

    def dump(self) -> typing.Tuple[typing.Mapping[str, typing.Any], ...]:
        return tuple(response.dump() for response in self.responses)


@dataclass
class JsonRpcUnlinkedResults:
    results: typing.MutableSequence = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.results) > 0

    def add(self, value: typing.Any) -> None:
        self.results.append(value)


@dataclass
class JsonRpcDuplicatedResults:
    results: typing.MutableSequence = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.results) > 0

    def add(self, value: typing.Any) -> None:
        self.results.append(value)
