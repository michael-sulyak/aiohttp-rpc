import typing
from dataclasses import dataclass, field

from .. import constants, errors, utils


__all__ = (
    'JsonRpcResponse',
)


@dataclass
class JsonRpcResponse:
    jsonrpc: str = constants.VERSION_2_0
    msg_id: typing.Any = constants.NOTHING
    result: typing.Any = constants.NOTHING
    error: typing.Optional[errors.JsonRpcError] = None
    context: dict = field(default_factory=dict)

    @property
    def is_notification(self) -> bool:
        return self.msg_id is constants.NOTHING

    @classmethod
    def from_dict(cls, data: dict, *, error_map: typing.Optional[dict] = None, **kwargs) -> 'JsonRpcResponse':
        cls._validate_json_response(data)

        response = cls(
            msg_id=data.get('id', constants.NOTHING),
            jsonrpc=data.get('jsonrpc', constants.VERSION_2_0),
            result=data.get('result'),
            **kwargs,
        )

        if 'error' in data:
            cls._add_error(response, data['error'], error_map=error_map)

        return response

    def to_dict(self) -> typing.Optional[dict]:
        if self.msg_id is constants.NOTHING:
            return None

        data = {'id': self.msg_id, 'jsonrpc': self.jsonrpc}

        if self.error is constants.NOTHING:
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
