import asyncio
import json
import logging
import typing

import aiohttp
from aiohttp import web_ws

from .base import BaseJsonRpcClient
from .. import errors, utils


__all__ = (
    'WsJsonRpcClient',
    'WsJsonRpcClientForResponse',
)

logger = logging.getLogger(__name__)


class WsJsonRpcClient(BaseJsonRpcClient):
    ws_connect: typing.Optional[aiohttp.ClientWebSocketResponse]
    notify_about_result: typing.Optional[typing.Callable] = None
    timeout: typing.Optional[int]
    ws_connect_kwargs: dict
    _pending: typing.Dict[typing.Any, asyncio.Future]
    _message_worker: typing.Optional[asyncio.Future] = None
    _session_is_outer: bool
    _ws_connect_is_outer: bool
    _json_request_handler: typing.Optional[typing.Callable] = None
    _unprocessed_json_response_handler: typing.Optional[typing.Callable] = None

    def __init__(self,
                 url: str, *,
                 session: typing.Optional[aiohttp.ClientSession] = None,
                 ws_connect: typing.Optional[aiohttp.ClientWebSocketResponse] = None,
                 timeout: typing.Optional[int] = 5,
                 json_request_handler: typing.Optional[typing.Callable] = None,
                 unprocessed_json_response_handler: typing.Optional[typing.Callable] = None,
                 **ws_connect_kwargs) -> None:
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
        if not self.session:
            self.session = aiohttp.ClientSession(json_serialize=self.json_serialize)

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
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        if without_response:
            await self.ws_connect.send_str(self.json_serialize(data))
            return None, None

        msg_ids = self._get_msg_ids_from_json(data)
        future = asyncio.Future()

        for msg_id in msg_ids:
            self._pending[msg_id] = future

        await self.ws_connect.send_str(self.json_serialize(data))

        if not msg_ids:
            return None, None

        if self.timeout is not None:
            future = asyncio.wait_for(future, timeout=self.timeout)

        result = await future

        return result, None

    def clear_pending(self) -> None:
        self._pending.clear()

    @staticmethod
    def _get_msg_ids_from_json(data: typing.Any) -> typing.Optional[list]:
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
        while not self.ws_connect.closed:
            try:
                ws_msg = await self.ws_connect.receive()
                asyncio.ensure_future(self._handle_ws_message(ws_msg))
            except asyncio.CancelledError as e:
                error = errors.ServerError(utils.get_exc_message(e)).with_traceback()
                self._notify_all_about_error(error)
                raise
            except Exception as e:
                logger.exception(e)

    async def _handle_ws_message(self, ws_msg: aiohttp.WSMessage) -> None:
        if ws_msg.type != aiohttp.WSMsgType.text:
            return

        json_response = json.loads(ws_msg.data)

        if not json_response:
            return

        if isinstance(json_response, dict):
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

            return

        if isinstance(json_response, list):
            if isinstance(json_response[0], dict) and 'method' in json_response[0]:
                if self._json_request_handler:
                    await self._json_request_handler(ws_connect=self.ws_connect, ws_msg=ws_msg)
            else:
                msg_ids = self._get_msg_ids_from_json(json_response)

                if msg_ids:
                    self._notify_about_results(msg_ids, json_response)
                else:
                    self._unprocessed_json_response_handler(
                        ws_connect=self.ws_connect,
                        ws_msg=ws_msg,
                        json_response=json_response,
                    )


    def _notify_all_about_error(self, error: errors.JsonRpcError) -> None:
        for future in self._pending.values():
            future.set_exception(error)

        self.clear_pending()

    def _notify_about_result(self, msg_id: typing.Any, json_response: dict) -> None:
        future = self._pending.pop(msg_id, None)

        if future:
            future.set_result(json_response)

    def _notify_about_results(self, msg_ids: list, json_response: list) -> None:
        is_processed = False

        for msg_id in msg_ids:
            future = self._pending.pop(msg_id, None)

            if future and not is_processed:
                future.set_result(json_response)
                is_processed = True


class WsJsonRpcClientForResponse(BaseJsonRpcClient):
    ws_response: web_ws.WebSocketResponse

    def __init__(self, ws_response: web_ws.WebSocketResponse) -> None:
        self.ws_response = ws_response

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def send_json(self,
                        data: typing.Any, *,
                        without_response: bool = False) -> typing.Tuple[typing.Any, typing.Optional[dict]]:
        assert without_response

        await self.ws_response.send_str(self.json_serialize(data))
        return None, None

    async def direct_call(self, *args, **kwargs):
        raise NotImplementedError

    async def direct_batch(self, *args, **kwargs):
        raise NotImplementedError
