import sys
import traceback
import typing


__all__ = (
    'JSONRPCError',
    'ServerError',
    'ParseError',
    'InvalidRequest',
    'MethodNotFound',
    'InvalidParams',
    'InternalError',
    'EmptyResponse',
    'RequestTimeoutError',
    'DEFAULT_KNOWN_ERRORS',
)


class JSONRPCError(RuntimeError):
    code: int
    message: str
    data: typing.Optional[typing.Any] = None

    def __init__(self,
                 message: typing.Optional[str] = None, *,
                 data: typing.Optional[typing.Any] = None,
                 code: typing.Optional[int] = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)
        self.data = data
        self.code = code or self.code

        assert self.code, 'Error without a code is not allowed.'
        assert self.message, 'Error without a message is not allowed.'

    def __repr__(self) -> str:
        msg = self.message.replace('\'', '\\\'')
        return f'{self.__class__.__name__}({self.code}, \'{msg}\')'

    def __str__(self) -> str:
        return self.message

    def __eq__(self, other: typing.Any) -> bool:
        return (
            isinstance(other, JSONRPCError)
            and self.code == other.code
            and self.message == other.message
            and self.data == other.data
        )

    def attach_traceback(self, traceback_exception=None) -> None:
        if not traceback_exception:
            traceback_exception = traceback.TracebackException(*sys.exc_info())

        if self.data is None:
            self.data = {}

        if isinstance(self.data, typing.MutableMapping):
            self.data['traceback_exception'] = ''.join(traceback_exception.format()).split('\n')


class ServerError(JSONRPCError):
    code = -32000
    message = 'Server error.'


class ParseError(JSONRPCError):
    code = -32700
    message = 'Parse error'


class InvalidRequest(JSONRPCError):
    code = -32600
    message = 'Invalid Request'


class MethodNotFound(JSONRPCError):
    code = -32601
    message = 'Method not found'


class InvalidParams(JSONRPCError):
    code = -32602
    message = 'Invalid params'


class InternalError(JSONRPCError):
    code = -32603
    message = 'Internal error'


class EmptyResponse(JSONRPCError):
    """It's error occurs on the client side when there are no responses."""

    code = -32050
    message = 'Empty Response'


class RequestTimeoutError(JSONRPCError):
    """It's error occurs on the client side when we didn't receive a response on time."""

    code = -32051
    message = 'Timeout error'


DEFAULT_KNOWN_ERRORS = frozenset({
    ServerError,
    ParseError,
    InvalidRequest,
    MethodNotFound,
    InvalidParams,
    InternalError,
    # Local errors:
    # EmptyResponse,
    # RequestTimeoutError,
})
