import typing
from dataclasses import dataclass, field

from .. import constants, errors, utils


__all__ = (
    'JsonRpcResponse',
    'JsonRpcBatchResponse',
    'UnlinkedResults',
    'DuplicatedResults',
)


@dataclass
class JsonRpcResponse:
    jsonrpc: str = constants.VERSION_2_0
    id: typing.Any = constants.NOTHING
    result: typing.Any = constants.NOTHING
    error: typing.Optional[errors.JsonRpcError] = None
    context: dict = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.id in constants.EMPTY_VALUES

    @classmethod
    def from_dict(cls, data: dict, *, error_map: typing.Optional[dict] = None, **kwargs) -> 'JsonRpcResponse':
        cls._validate_json_response(data)

        response = cls(
            id=data.get('id', constants.NOTHING),
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            result=data.get('result'),
            **kwargs,
        )

        if 'error' in data:
            cls._add_error(response, data['error'], error_map=error_map)

        return response

    def to_dict(self) -> typing.Optional[dict]:
        data = {'jsonrpc': self.jsonrpc}

        if self.id in constants.EMPTY_VALUES:
            data['id'] = None
        else:
            data['id'] = self.id

        if self.error in constants.EMPTY_VALUES:
            data['result'] = self.result
        else:
            data['error'] = {'code': self.error.code, 'message': self.error.message}

            if self.error.data is not None:
                data['error']['data'] = self.error.data

        return data

    @staticmethod
    def _validate_json_response(data: typing.Any) -> None:
        if not isinstance(data, dict):
            raise errors.InvalidRequest

        utils.validate_jsonrpc(data.get('jsonrpc'))

        if 'result' not in data and 'error' not in data:
            raise errors.InvalidRequest('"result" or "error" not found in data.', data={'raw_response': data})

    @staticmethod
    def _add_error(response: 'JsonRpcResponse', error: typing.Any, *, error_map: typing.Optional[dict] = None) -> None:
        if not isinstance(error, dict):
            raise errors.InvalidRequest

        if not ({'code', 'message'}) <= error.keys():
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
    responses: typing.List[JsonRpcResponse] = field(default_factory=list)

    def to_list(self) -> typing.List[dict]:
        return [response.to_dict() for response in self.responses]

    @classmethod
    def from_list(cls, data: list, *, error_map: typing.Optional[dict] = None, **kwargs) -> 'JsonRpcBatchResponse':
        responses = [
            JsonRpcResponse.from_dict(item, error_map=error_map, **kwargs)
            for item in data
        ]

        return cls(responses=responses)


@dataclass
class UnlinkedResults:
    data: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.data) > 0

    def get(self) -> list:
        return self.data

    def add(self, value: typing.Any) -> None:
        self.data.append(value)


@dataclass
class DuplicatedResults:
    data: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return len(self.data) > 0

    def get(self) -> list:
        return self.data

    def add(self, value: typing.Any) -> None:
        self.data.append(value)
