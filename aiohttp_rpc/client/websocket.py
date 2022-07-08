import asyncio
import json
import logging
import typing

from aiohttp import ClientSession, http_websocket, web_ws

from .base import BaseJsonRpcClient
from .. import errors, typedefs, utils


__all__ = (
    'WsJsonRpcClient',
)

logger = logging.getLogger(__name__)


class WsJsonRpcClient(BaseJsonRpcClient):
    url: typing.Optional[str]
    ws_connect: typing.Optional[typedefs.WSConnectType]
    ws_connect_kwargs: dict
    timeout: typing.Optional[int]
    _pending: typing.Dict[typing.Any, asyncio.Future]
    _message_worker: typing.Optional[asyncio.Future] = None
    _session_is_outer: bool
    _ws_connect_is_outer: bool
    _json_request_handler: typing.Optional[typing.Callable] = None
    _unprocessed_json_response_handler: typing.Optional[typing.Callable] = None
    _background_tasks: typing.Set

    def __init__(self,
                 url: typing.Optional[str] = None, *,
                 session: typing.Optional[ClientSession] = None,
                 ws_connect: typing.Optional[typedefs.WSConnectType] = None,
                 timeout: typing.Optional[int] = 5,
                 json_request_handler: typing.Optional[typing.Callable] = None,
                 unprocessed_json_response_handler: typing.Optional[typing.Callable] = None,
                 **ws_connect_kwargs) -> None:
        assert (session is not None) or (url is not None and session is None) or (ws_connect is not None)

        self.url = url
        self.timeout = timeout

        self.session = session
        self._session_is_outer = session is not None  # We don't close an outer session.

        self.ws_connect = ws_connect
        self.ws_connect_kwargs = ws_connect_kwargs
        self._ws_connect_is_outer = ws_connect is not None  # We don't close an outer WS connection.

        self._pending = {}
        self._json_request_handler = json_request_handler
        self._unprocessed_json_response_handler = unprocessed_json_response_handler
        self._background_tasks = set()

    async def connect(self) -> None:
        if self.session is None and self.ws_connect is None:
            self.session = ClientSession(json_serialize=self.json_serialize)

        if self.ws_connect is None:
            assert self.url is not None and self.session is not None

            try:
                self.ws_connect = await self.session.ws_connect(self.url, **self.ws_connect_kwargs)
            except Exception:
                await self.disconnect()
                raise

        self._message_worker = asyncio.create_task(self._handle_ws_messages())

    async def disconnect(self) -> None:
        if self.ws_connect is not None and not self._ws_connect_is_outer:
            await self.ws_connect.close()

        if self.session is not None and not self._session_is_outer:
            await self.session.close()

        if self._message_worker is not None:
            await self._message_worker

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        assert self.ws_connect is not None

        if without_response:
            await self.ws_connect.send_str(self.json_serialize(data), **kwargs)
            return None, None

        request_ids = self._get_ids_from_json(data)
        future: asyncio.Future = asyncio.Future()

        for request_id in request_ids:
            self._pending[request_id] = future

        await self.ws_connect.send_str(self.json_serialize(data), **kwargs)

        if not request_ids:
            return None, None

        if self.timeout is not None:
            future = asyncio.wait_for(future, timeout=self.timeout)  # type: ignore

        result = await future

        return result, None

    def clear_pending(self) -> None:
        self._pending.clear()

    @staticmethod
    def _get_ids_from_json(data: typing.Any) -> typing.Tuple[typedefs.JsonRpcIdType, ...]:
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

        ws_msg: http_websocket.WSMessage

        async for ws_msg in self.ws_connect:
            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            try:
                task = asyncio.create_task(self._handle_single_ws_message(ws_msg))
            except asyncio.CancelledError as e:
                error = errors.ServerError(utils.get_exc_message(e)).with_traceback()
                self._notify_all_about_error(error)
                raise
            except Exception:
                logger.warning('Can not process WS message.', exc_info=True)
            else:
                # To avoid a task disappearing mid execution:
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

    async def _handle_single_ws_message(self, ws_msg: http_websocket.WSMessage) -> None:
        if ws_msg.type != http_websocket.WSMsgType.text:
            return

        try:
            json_response = json.loads(ws_msg.data)
        except Exception:
            logger.warning('Cann\'t parse json.', exc_info=True)
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
        if 'method' in json_response:
            if self._json_request_handler is not None:
                await self._json_request_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_request=json_response,
                )
        elif 'id' in json_response and json_response['id'] in self._pending:
            self._notify_about_result(json_response['id'], json_response)
        elif self._unprocessed_json_response_handler is not None:
            self._unprocessed_json_response_handler(
                ws_connect=self.ws_connect,
                ws_msg=ws_msg,
                json_response=json_response,
            )

    async def _handle_json_responses(self, json_responses: typing.Sequence, *, ws_msg: web_ws.WSMessage) -> None:
        if isinstance(json_responses[0], typing.Mapping) and 'method' in json_responses[0]:
            if self._json_request_handler is not None:
                await self._json_request_handler(ws_connect=self.ws_connect, ws_msg=ws_msg)
        else:
            response_ids = self._get_ids_from_json(json_responses)

            if response_ids:
                self._notify_about_results(response_ids, json_responses)
            elif self._unprocessed_json_response_handler is not None:
                self._unprocessed_json_response_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_response=json_responses,
                )

    def _notify_all_about_error(self, error: errors.JsonRpcError) -> None:
        for future in self._pending.values():
            future.set_exception(error)

        self.clear_pending()

    def _notify_about_result(self, response_id: typedefs.JsonRpcIdType, json_response: typing.Mapping) -> None:
        future = self._pending.pop(response_id, None)

        if future is not None:
            future.set_result(json_response)

    def _notify_about_results(self,
                              response_ids: typing.Sequence[typedefs.JsonRpcIdType],
                              json_response: typing.Sequence) -> None:
        is_processed = False

        for response_id in response_ids:
            future = self._pending.pop(response_id, None)

            if future is not None and not is_processed:
                # We suppose that a batch result has the same ids that we sent.
                # And this ids have the same future.

                future.set_result(json_response)
                is_processed = True
