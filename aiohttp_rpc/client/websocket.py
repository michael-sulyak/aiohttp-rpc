import asyncio
import json
import logging
import typing

from aiohttp import ClientSession, client_ws, http_websocket, web_ws

from .base import BaseJsonRpcClient
from .. import errors, utils


__all__ = (
    'WsJsonRpcClient',
)

logger = logging.getLogger(__name__)

WSConnectType = typing.Union[client_ws.ClientWebSocketResponse, web_ws.WebSocketResponse]


class WsJsonRpcClient(BaseJsonRpcClient):
    url: typing.Optional[str]
    ws_connect: typing.Optional[WSConnectType]
    timeout: typing.Optional[int]
    ws_connect_kwargs: dict
    _pending: typing.Dict[typing.Any, asyncio.Future]
    _message_worker: typing.Optional[asyncio.Future] = None
    _session_is_outer: bool
    _ws_connect_is_outer: bool
    _json_request_handler: typing.Optional[typing.Callable] = None
    _unprocessed_json_response_handler: typing.Optional[typing.Callable] = None

    def __init__(self,
                 url: typing.Optional[str] = None, *,
                 session: typing.Optional[ClientSession] = None,
                 ws_connect: typing.Optional[WSConnectType] = None,
                 timeout: typing.Optional[int] = 5,
                 json_request_handler: typing.Optional[typing.Callable] = None,
                 unprocessed_json_response_handler: typing.Optional[typing.Callable] = None,
                 **ws_connect_kwargs) -> None:
        assert (session is not None) or (url is not None and session is None) or (ws_connect is not None)

        self.url = url
        self.timeout = timeout

        self.session = session
        self._session_is_outer = session is not None

        self.ws_connect = ws_connect
        self.ws_connect_kwargs = ws_connect_kwargs
        self._ws_connect_is_outer = ws_connect is not None

        self._pending = {}
        self._json_request_handler = json_request_handler
        self._unprocessed_json_response_handler = unprocessed_json_response_handler

    async def connect(self) -> None:
        if not self.session and not self.ws_connect:
            self.session = ClientSession(json_serialize=self.json_serialize)

        if not self.ws_connect:
            try:
                self.ws_connect = await self.session.ws_connect(self.url, **self.ws_connect_kwargs)
            except Exception:
                await self.disconnect()
                raise

        self._message_worker = asyncio.ensure_future(self._handle_ws_messages())

    async def disconnect(self) -> None:
        if self.ws_connect and not self._ws_connect_is_outer:
            await self.ws_connect.close()

        if self.session and not self._session_is_outer:
            await self.session.close()

        if self._message_worker:
            await self._message_worker

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False,
                        **kwargs) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        if without_response:
            await self.ws_connect.send_str(self.json_serialize(data), **kwargs)
            return None, None

        request_ids = self._get_ids_from_json(data)
        future = asyncio.Future()

        for request_id in request_ids:
            self._pending[request_id] = future

        await self.ws_connect.send_str(self.json_serialize(data), **kwargs)

        if not request_ids:
            return None, None

        if self.timeout is not None:
            future = asyncio.wait_for(future, timeout=self.timeout)

        result = await future

        return result, None

    def clear_pending(self) -> None:
        self._pending.clear()

    @staticmethod
    def _get_ids_from_json(data: typing.Any) -> typing.Optional[list]:
        if not data:
            return []

        if isinstance(data, dict) and data.get('id') is not None:
            return [data['id']]

        if isinstance(data, list):
            return [
                item['id']
                for item in data
                if isinstance(item, dict) and item.get('id') is not None
            ]

        return []

    async def _handle_ws_messages(self) -> typing.NoReturn:
        async for ws_msg in self.ws_connect:
            if ws_msg.type != http_websocket.WSMsgType.TEXT:
                continue

            try:
                asyncio.ensure_future(self._handle_single_ws_message(ws_msg))
            except asyncio.CancelledError as e:
                error = errors.ServerError(utils.get_exc_message(e)).with_traceback()
                self._notify_all_about_error(error)
                raise
            except Exception:
                logger.warning('Can not process WS message.', exc_info=True)

    async def _handle_single_ws_message(self, ws_msg: http_websocket.WSMessage) -> None:
        if ws_msg.type != http_websocket.WSMsgType.text:
            return

        try:
            json_response = json.loads(ws_msg.data)
        except Exception:
            logger.warning('Can not parse json.', exc_info=True)
            return

        if not json_response:
            return

        if isinstance(json_response, dict):
            await self._handle_single_json_response(json_response, ws_msg=ws_msg)
            return

        if isinstance(json_response, list):
            await self._handle_json_responses(json_response, ws_msg=ws_msg)
            return

        logger.warning('Couldn\'t process the response.', extra={
            'json_response': json_response,
        })

    async def _handle_single_json_response(self, json_response: dict, *, ws_msg: web_ws.WSMessage) -> None:
        if 'method' in json_response:
            if self._json_request_handler:
                await self._json_request_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_request=json_response,
                )
        elif 'id' in json_response and json_response['id'] in self._pending:
            self._notify_about_result(json_response['id'], json_response)
        elif self._unprocessed_json_response_handler:
            self._unprocessed_json_response_handler(
                ws_connect=self.ws_connect,
                ws_msg=ws_msg,
                json_response=json_response,
            )

    async def _handle_json_responses(self, json_responses: list, *, ws_msg: web_ws.WSMessage) -> None:
        if isinstance(json_responses[0], dict) and 'method' in json_responses[0]:
            if self._json_request_handler:
                await self._json_request_handler(ws_connect=self.ws_connect, ws_msg=ws_msg)
        else:
            response_ids = self._get_ids_from_json(json_responses)

            if response_ids:
                self._notify_about_results(response_ids, json_responses)
            else:
                self._unprocessed_json_response_handler(
                    ws_connect=self.ws_connect,
                    ws_msg=ws_msg,
                    json_response=json_responses,
                )

    def _notify_all_about_error(self, error: errors.JsonRpcError) -> None:
        for future in self._pending.values():
            future.set_exception(error)

        self.clear_pending()

    def _notify_about_result(self, response_id: typing.Any, json_response: dict) -> None:
        future = self._pending.pop(response_id, None)

        if future:
            future.set_result(json_response)

    def _notify_about_results(self, response_ids: list, json_response: list) -> None:
        is_processed = False

        for response_id in response_ids:
            future = self._pending.pop(response_id, None)

            if future and not is_processed:
                future.set_result(json_response)
                is_processed = True
