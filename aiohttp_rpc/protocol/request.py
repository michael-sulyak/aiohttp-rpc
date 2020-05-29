import typing
from dataclasses import dataclass, field

from .. import constants, errors, utils


__all__ = (
    'JsonRpcRequest',
)


@dataclass
class JsonRpcRequest:
    method: str
    msg_id: typing.Any = constants.NOTHING
    jsonrpc: str = constants.VERSION_2_0
    extra_args: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    params: typing.Any = constants.NOTHING
    args: typing.Optional[typing.Union[list, tuple]] = None
    kwargs: typing.Optional[dict] = None

    def __post_init__(self):
        utils.validate_jsonrpc(self.jsonrpc)

        if self.params is constants.NOTHING:
            self.set_args_and_kwargs(self.args, self.kwargs)
        elif not self.args and not self.kwargs:
            self.set_params(self.params)
        else:
            raise errors.InvalidParams('Need use params or args with kwargs.')

    def set_params(self, params: typing.Any) -> None:
        self.params = params
        self.args, self.kwargs = utils.convert_params_to_args_and_kwargs(params)

    def set_args_and_kwargs(self, args: typing.Optional[list] = None, kwargs: typing.Optional[dict] = None) -> None:
        self.params, self.args, self.kwargs = utils.parse_args_and_kwargs(args, kwargs)

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
