import sys
import traceback
import typing


__all__ = (
    'JsonRpcError',
    'ServerError',
    'ParseError',
    'InvalidRequest',
    'MethodNotFound',
    'InvalidParams',
    'InternalError',
    'DEFAULT_KNOWN_ERRORS',
)


class JsonRpcError(RuntimeError):
    code: typing.Optional[int] = None
    message: typing.Optional[str] = None
    data: typing.Optional[typing.Any] = None

    def __init__(self,
                 message: typing.Optional[str] = None, *,
                 data: typing.Optional[typing.Any] = None,
                 code: typing.Optional[typing.Any] = None) -> None:
        super().__init__(self)
        self.message = message or self.message
        self.data = data
        self.code = code or self.code
        assert self.code, 'Error without code is not allowed.'

    def __repr__(self) -> str:
        return f'JsonRpcError({self.code}): {self.message}'

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: typing.Any) -> bool:
        return (
                isinstance(other, JsonRpcError)
                and self.code == other.code
                and self.message == other.message
                and self.data == other.data
        )

    def with_traceback(self, exc_info=None, traceback_exception=None) -> 'JsonRpcError':
        if not traceback_exception:
            traceback_exception = traceback.TracebackException(*sys.exc_info())

        if self.data is None:
            self.data = {}

        if isinstance(self.data, dict):
            self.data['traceback_exception'] = ''.join(traceback_exception.format()).split("\n")

        return self


class ServerError(JsonRpcError):
    code = -32000
    message = 'Server error.'


class ParseError(JsonRpcError):
    code = -32700
    message = 'Invalid JSON was received by the server.'


class InvalidRequest(JsonRpcError):
    code = -32600
    message = 'The JSON sent is not a valid Request object.'


class MethodNotFound(JsonRpcError):
    code = -32601
    message = 'The method does not exist / is not available.'


class InvalidParams(JsonRpcError):
    code = -32602
    message = 'Invalid method parameter(s).'


class InternalError(JsonRpcError):
    code = -32603
    message = 'Internal JSON-RPC error.'


DEFAULT_KNOWN_ERRORS = frozenset({
    ServerError,
    ParseError,
    InvalidRequest,
    MethodNotFound,
    InvalidParams,
    InternalError,
})
