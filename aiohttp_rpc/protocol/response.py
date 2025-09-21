import typing
from dataclasses import dataclass, field

from .. import constants, errors, typedefs, utils


__all__ = (
    'JSONRPCResponse',
    'JSONRPCBatchResponse',
    'JSONRPCUnlinkedResults',
    'JSONRPCDuplicatedResults',
)


@dataclass
class JSONRPCResponse:
    id: typing.Optional[typedefs.JSONRPCIDType] = None
    jsonrpc: str = constants.VERSION_2_0
    result: typing.Any = None
    error: typing.Optional[errors.JSONRPCError] = None
    context: typing.MutableMapping = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.id is None

    @classmethod
    def load(cls,
             data: typing.Any, *,
             error_map: typing.Optional[typing.Mapping] = None, **kwargs) -> 'JSONRPCResponse':
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
            raise errors.ParseError('Data must be a mapping.')

        utils.validate_jsonrpc(data.get('jsonrpc'))

        has_result = 'result' in data
        has_error = 'error' in data

        if not has_result and not has_error:
            raise errors.ParseError('"result" or "error" not found in data.', data={'raw_response': data})

        if has_result and has_error:
            raise errors.ParseError('Response must not include both "result" and "error".', data={'raw_response': data})

    @staticmethod
    def _add_error(response: 'JSONRPCResponse',
                   error: typing.Any, *,
                   error_map: typing.Optional[typing.Mapping] = None) -> None:
        if not isinstance(error, typing.Mapping):
            raise errors.ParseError(
                'The "error" field must be a mapping.',
                data={'raw_error': error},
            )

        if not {'code', 'message'} <= error.keys():
            raise errors.ParseError(
                'The "error" field must contain "code" and "message".',
                data={'raw_error': error},
            )

        if error_map:
            exception_class = error_map.get(error['code'], errors.JSONRPCError)
        else:
            exception_class = errors.JSONRPCError

        response.error = exception_class(
            message=error['message'],
            data=error.get('data'),
            code=error['code'],
        )


@dataclass
class JSONRPCBatchResponse:
    responses: typing.Tuple[JSONRPCResponse, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls,
             data: typing.Any, *,
             error_map: typing.Optional[typing.Mapping] = None,
             **kwargs) -> 'JSONRPCBatchResponse':
        if isinstance(data, typing.Mapping):
            parsed_response = JSONRPCResponse.load(data, error_map=error_map, **kwargs)

            if parsed_response.error:
                raise parsed_response.error
            else:
                raise errors.ParseError('Got an unexpected response from server.')

        if not isinstance(data, typing.Sequence):
            raise errors.InvalidRequest('Batch request must be of the list type.')

        return cls(responses=tuple(
            JSONRPCResponse.load(item, error_map=error_map, **kwargs)
            for item in data
        ))

    def dump(self) -> typing.Tuple[typing.Mapping[str, typing.Any], ...]:
        return tuple(response.dump() for response in self.responses)


@dataclass
class JSONRPCUnlinkedResults:
    results: typing.MutableSequence = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.results) > 0

    def add(self, value: typing.Any) -> None:
        self.results.append(value)


@dataclass
class JSONRPCDuplicatedResults:
    results: typing.MutableSequence = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.results) > 0

    def add(self, value: typing.Any) -> None:
        self.results.append(value)
