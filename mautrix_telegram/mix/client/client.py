# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2020 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Tuple, Dict, Optional
import logging
import asyncio
import sys

from ..protocol import Command, Response, write, read
from .lock import MixLock


class MixError(Exception):
    def __init__(self, message: str, response: Response, payload: bytes) -> None:
        super().__init__(message)
        self.response = response
        self.payload = payload


class UnexpectedResponse(MixError):
    def __init__(self, response: Response, payload: bytes) -> None:
        super().__init__(f"Unexpected response: {response.name}", response, payload)


class ServerError(MixError):
    def __init__(self, payload: bytes) -> None:
        super().__init__(f"Server error: {payload.decode('utf-8')}", Response.ERROR, payload)


class MixClient:
    log: logging.Logger = logging.getLogger("mau.mix.client")
    loop: asyncio.AbstractEventLoop
    unix: bool
    host: str
    port: int
    conn_id: str
    conn_name: str
    _req_id: int
    _writer: asyncio.StreamWriter
    _reader: asyncio.StreamReader
    _ongoing_commands: Dict[int, asyncio.Future]
    _listen_fut: Optional[asyncio.Future]

    def __init__(self, host: str, port: int, unix: bool, conn_id: str,
                 conn_name: Optional[str] = None, loop: Optional[asyncio.AbstractEventLoop] = None
                 ) -> None:
        self.unix = unix
        self.host = host
        self.port = port
        self._req_id = 0
        self.conn_id = conn_id
        self.conn_name = conn_name or conn_id
        self.loop = loop or asyncio.get_event_loop()
        self._listen_fut = None

    @property
    def next_req_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def call(self, cmd: Command, payload: bytes,
                   expected_responses: Optional[Tuple[Response, ...]] = None
                   ) -> Tuple[Response, bytes]:
        future = self.loop.create_future()
        req_id = self.next_req_id
        self._ongoing_commands[req_id] = future
        await write(self._writer, req_id, cmd, payload)
        resp, payload = await future
        if resp == Response.ERROR:
            raise ServerError(payload)
        elif expected_responses and resp not in expected_responses:
            raise UnexpectedResponse(resp, payload)
        return resp, payload

    async def connect(self) -> None:
        if self.unix:
            conn = await asyncio.open_unix_connection(self.host, loop=self.loop)
        else:
            conn = await asyncio.open_connection(self.host, self.port, loop=self.loop)
        self._reader, self._writer = conn
        await write(self._writer, 0, Command.CONNECT,
                    f"{self.conn_id};{self.conn_name}".encode("utf-8"))
        self.log.info("Connected")

    def listen(self) -> None:
        self._listen_fut = asyncio.ensure_future(self._listen(), loop=self.loop)

    async def _listen(self) -> None:
        try:
            while True:
                try:
                    req_id, resp, payload = await read(self._reader)
                except asyncio.IncompleteReadError:
                    self.log.warning("Incomplete read, disconnecting...")
                    break
                except Exception:
                    self.log.exception("Error in reader, disconnecting...")
                    break
                self.log.debug(f"Received response to #{req_id}: {resp.name}")
                future = self._ongoing_commands.pop(req_id)
                if future:
                    future.set_result((resp, payload))
        except asyncio.CancelledError:
            self.log.info("Reader cancelled, disconnecting...")
        for fut in self._ongoing_commands.values():
            fut.cancel()
        try:
            self._writer.write_eof()
            await self._writer.drain()
        except Exception:
            pass
        self._writer.close()
        if sys.version_info >= (3, 7):
            await self._writer.wait_closed()
        self.log.info("Disconnected")

    def stop(self) -> None:
        if self._listen_fut:
            self._listen_fut.cancel()
