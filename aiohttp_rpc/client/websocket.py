import asyncio
import contextlib
import logging
import typing

from aiohttp import ClientSession, http_websocket, web_ws

from .base import BaseJSONRPCClient
from .. import errors, typedefs, utils


__all__ = (
    'WSJSONRPCClient',
)

logger = logging.getLogger(__name__)


class WSJSONRPCClient(BaseJSONRPCClient):
    url: typing.Optional[str]
    ws_connect: typing.Optional[typedefs.WSConnectType]
    ws_connect_kwargs: dict
    _timeout: typing.Optional[float]
    _timeout_for_data_receiving: typing.Optional[float]
    _connection_check_interval: typing.Optional[float]
    _pending: typing.Dict[typing.Any, asyncio.Future]
    _message_worker: typing.Optional[asyncio.Future] = None
    _check_worker: typing.Optional[asyncio.Future] = None
    _session_is_outer: bool
    _ws_connect_is_outer: bool
    _json_requests_handler: typing.Optional[typedefs.WSJSONRequestsHandler]
    _unprocessed_json_responses_handler: typing.Optional[typedefs.UnprocessedWSJSONResponsesHandler]
    _background_tasks: typing.Set
    _is_closed: bool = True

    def __init__(self,
                 url: typing.Optional[str] = None, *,
                 session: typing.Optional[ClientSession] = None,
                 ws_connect: typing.Optional[typedefs.WSConnectType] = None,
                 timeout: typing.Optional[float] = 60,
                 timeout_for_data_receiving: typing.Optional[float] = 60,
                 connection_check_interval: typing.Optional[float] = 5,
                 json_requests_handler: typing.Optional[typedefs.WSJSONRequestsHandler] = None,
                 unprocessed_json_responses_handler: typing.Optional[typedefs.UnprocessedWSJSONResponsesHandler] = None,
                 json_serialize: typedefs.JSONEncoderType = utils.json_serialize,
                 json_deserialize: typedefs.JSONDecoderType = utils.json_deserialize,
                 **ws_connect_kwargs) -> None:
        assert ws_connect is not None or url is not None

        super().__init__(
            json_serialize=json_serialize,
            json_deserialize=json_deserialize,
        )

        self.url = url
        self._timeout = timeout
        self._timeout_for_data_receiving = timeout_for_data_receiving
        self._connection_check_interval = connection_check_interval

        self.session = session
        self._session_is_outer = session is not None  # We don't close an outer session.

        self.ws_connect = ws_connect
        self.ws_connect_kwargs = ws_connect_kwargs
        self._ws_connect_is_outer = ws_connect is not None  # We don't close an outer WS connection.

        self._pending = {}
        self._json_requests_handler = json_requests_handler
        self._unprocessed_json_responses_handler = unprocessed_json_responses_handler
        self._background_tasks = set()

    async def connect(self) -> None:
        self._is_closed = False

        if self.session is None and self.ws_connect is None:
            self.session = ClientSession(json_serialize=self._json_serialize)

        if self.ws_connect is None:
            assert self.url is not None and self.session is not None

            try:
                self.ws_connect = await self.session.ws_connect(self.url, **self.ws_connect_kwargs)
            except Exception:
                await self.disconnect()
                raise

        self._message_worker = asyncio.create_task(self._handle_ws_messages())

        if self._connection_check_interval is not None:
            self._check_worker = asyncio.create_task(self._check_ws_connection())

    async def disconnect(self) -> None:
        self._is_closed = True

        # Fail pending before closing so callers don’t hang
        if self._pending:
            self._notify_all_about_error(errors.TransportError(data={'details': 'Client closed'}))

        if self._message_worker is not None:
            self._message_worker.cancel()  # ensure immediate exit

        if self.ws_connect is not None and not self._ws_connect_is_outer:
            await self.ws_connect.close()

        if self.session is not None and not self._session_is_outer:
            await self.session.close()

        if self._message_worker is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._message_worker

        if self._check_worker is not None:
            self._check_worker.cancel()
            await self._check_worker

        for task in tuple(self._background_tasks):
            task.cancel()

        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

    async def send_json(self,
                        data: typing.Any, *,
                        ignore_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:

        if ignore_response:
            await self._send_raw_data(self._json_serialize(data), **kwargs)
            return None, None

        request_ids = self._get_ids_from_json(data)
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        for request_id in request_ids:
            self._pending[request_id] = future

        await self._send_raw_data(self._json_serialize(data), **kwargs)

        if not request_ids:
            return None, None

        try:
            result = await asyncio.wait_for(future, timeout=self._timeout) if self._timeout is not None else future
        except asyncio.TimeoutError as e:
            for request_id in request_ids:
                self._pending.pop(request_id, None)

            raise errors.RequestTimeoutError from e
        except Exception:
            for request_id in request_ids:
                self._pending.pop(request_id, None)

            raise

        return result, None

    async def _send_raw_data(self, text: str, **kwargs) -> None:
        assert self.ws_connect is not None

        try:
            await self.ws_connect.send_str(text, **kwargs)
        except (ConnectionResetError, RuntimeError, OSError) as e:
            logger.warning('WS send failed', exc_info=True)
            error = errors.TransportError()
            self._notify_all_about_error(error)
            raise error from e

    @staticmethod
    def _get_ids_from_json(data: typing.Any) -> typing.Tuple[typedefs.JSONRPCIDType, ...]:
        if not data:
            return ()

        if isinstance(data, typing.Mapping) and data.get('id') is not None:
            return (
                data['id'],
            )

        if isinstance(data, typing.Sequence):
            return tuple(
                item['id']
                for item in data
                if isinstance(item, typing.Mapping) and item.get('id') is not None
            )

        return ()

    async def _handle_ws_messages(self) -> None:
        assert self.ws_connect is not None

        while True:
            try:
                ws_msg: http_websocket.WSMessage = await self.ws_connect.receive(
                    timeout=self._timeout_for_data_receiving,
                )
            except asyncio.TimeoutError:
                if self._is_closed:
                    break
                else:
                    continue

            if ws_msg.type in (
                    http_websocket.WSMsgType.CLOSE,
                    http_websocket.WSMsgType.CLOSING,
                    http_websocket.WSMsgType.CLOSED,
            ):
                break

            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            try:
                task = asyncio.create_task(self._handle_single_ws_message(ws_msg))
            except asyncio.CancelledError:
                logger.warning('Cancelled message handler on disconnect.', exc_info=True)
                error = errors.InternalError()
                self._notify_all_about_error(error)
                break
            except Exception:
                logger.warning('Can\'t process WS message.', exc_info=True)
            else:
                # To avoid a task disappearing mid execution:
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

            if self._is_closed:
                break

    async def _check_ws_connection(self) -> None:
        assert self.ws_connect is not None

        try:
            while not self._is_closed:
                if self.ws_connect.closed:
                    error = errors.ServerError(data={'details': 'Connection is closed.'})
                    self._notify_all_about_error(error)
                    break

                await asyncio.sleep(self._connection_check_interval)  # type: ignore
        except asyncio.CancelledError:
            pass

    async def _handle_single_ws_message(self, ws_msg: http_websocket.WSMessage) -> None:
        if ws_msg.type != http_websocket.WSMsgType.TEXT:
            return

        try:
            json_response = self._json_deserialize(ws_msg.data)
        except Exception:
            logger.warning('Can\'t parse json.', exc_info=True)
            return

        if not json_response:
            return

        if isinstance(json_response, typing.Mapping):
            await self._handle_single_json_response(json_response, ws_msg=ws_msg)
            return

        if isinstance(json_response, typing.Sequence):
            await self._handle_json_responses(json_response, ws_msg=ws_msg)
            return

        logger.warning('Couldn\'t process the response.', extra={
            'json_response': json_response,
        })

    async def _handle_single_json_response(self, json_response: typing.Mapping, *, ws_msg: web_ws.WSMessage) -> None:
        assert self.ws_connect is not None

        if 'method' in json_response:
            if self._json_requests_handler is not None:
                await self._json_requests_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_requests=(json_response,),
                )
        elif 'id' in json_response and json_response['id'] in self._pending:
            self._notify_about_result(json_response['id'], json_response)
        elif self._unprocessed_json_responses_handler is not None:
            await self._unprocessed_json_responses_handler(
                ws_connect=self.ws_connect,
                ws_msg=ws_msg,
                json_responses=(json_response,),
            )

    async def _handle_json_responses(self, json_responses: typing.Sequence, *, ws_msg: web_ws.WSMessage) -> None:
        assert self.ws_connect is not None

        if not json_responses:
            return

        if isinstance(json_responses[0], typing.Mapping) and 'method' in json_responses[0]:
            if self._json_requests_handler is not None:
                await self._json_requests_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_requests=json_responses,
                )
        else:
            response_ids = self._get_ids_from_json(json_responses)

            if response_ids:
                self._notify_about_results(response_ids, json_responses)
            elif self._unprocessed_json_responses_handler is not None:
                await self._unprocessed_json_responses_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_responses=json_responses,
                )

    def _notify_all_about_error(self, error: Exception) -> None:
        for future in self._pending.values():
            try:
                future.set_exception(error)
            except asyncio.InvalidStateError:
                pass

        self._pending.clear()

    def _notify_about_result(self, response_id: typedefs.JSONRPCIDType, json_response: typing.Mapping) -> None:
        future = self._pending.pop(response_id, None)

        if future is not None and not future.done():
            future.set_result(json_response)

    def _notify_about_results(self,
                              response_ids: typing.Sequence[typedefs.JSONRPCIDType],
                              json_response: typing.Sequence) -> None:
        is_processed = False

        for response_id in response_ids:
            future = self._pending.pop(response_id, None)

            if future is not None and not is_processed:
                # We suppose that a batch result has the same ids that we sent.
                # And these ids have the same future.

                future.set_result(json_response)
                is_processed = True
