import typing

from .. import constants, errors, utils


__all__ = (
    'JsonRpcRequest',
)


class JsonRpcRequest:
    msg_id: typing.Any
    method: str
    jsonrpc: str
    extra_args: dict
    context: dict
    _params: typing.Any
    _args: list
    _kwargs: dict

    def __init__(self, *,
                 msg_id: typing.Any = constants.NOTHING,
                 method: str,
                 jsonrpc: typing.Any = constants.VERSION_2_0,
                 params: typing.Any = constants.NOTHING,
                 args: typing.Any = None,
                 kwargs: typing.Any = None,
                 context: typing.Optional[dict] = None) -> None:
        utils.validate_jsonrpc(jsonrpc)

        self.msg_id = msg_id
        self.method = method
        self.jsonrpc = jsonrpc
        self.extra_args = {}
        self.context = {} if context is None else context

        if params is constants.NOTHING:
            self.args_and_kwargs = args, kwargs
        elif not args and not kwargs:
            self.params = params
        else:
            raise errors.InvalidParams('Need use params or args with kwargs.')

    @property
    def params(self) -> typing.Any:
        return self._params

    @params.setter
    def params(self, value: typing.Any) -> None:
        self._params = value
        self._args, self._kwargs = utils.convert_params_to_args_and_kwargs(value)

    @property
    def args(self) -> list:
        return self._args

    @property
    def kwargs(self) -> dict:
        return self._kwargs

    @property
    def args_and_kwargs(self) -> typing.Tuple[list, dict]:
        return self._args, self._kwargs

    @args_and_kwargs.setter
    def args_and_kwargs(self, value: typing.Tuple[typing.Optional[list], typing.Optional[dict]]) -> None:
        self._params, self._args, self._kwargs = utils.parse_args_and_kwargs(*value)

    @property
    def is_notification(self) -> bool:
        return self.msg_id is constants.NOTHING

    @classmethod
    def from_dict(cls, data: typing.Dict[str, typing.Any], **kwargs) -> 'JsonRpcRequest':
        cls._validate_json_request(data)

        return cls(
            msg_id=data.get('id', constants.NOTHING),
            method=data['method'],
            params=data.get('params', constants.NOTHING),
            jsonrpc=data['jsonrpc'],
            **kwargs,
        )

    def to_dict(self) -> dict:
        data = {
            'method': self.method,
            'jsonrpc': self.jsonrpc,
        }

        if not self.is_notification:
            data['id'] = self.msg_id

        if self.params is not constants.NOTHING:
            data['params'] = self.params

        return data

    @staticmethod
    def _validate_json_request(data: typing.Any) -> None:
        if not isinstance(data, dict):
            raise errors.InvalidRequest('A request must be of the dict type.')

        if not ({'method', 'jsonrpc'}) <= data.keys():
            raise errors.InvalidRequest('A request must contain "method" and "jsonrpc".')

        utils.validate_jsonrpc(data['jsonrpc'])
