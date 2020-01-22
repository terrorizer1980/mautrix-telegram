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
from typing import Optional, Tuple, Awaitable
import logging
import asyncio

from ..protocol import Command, Response
from ..handlers import ConnectionHandler
from ..errors import MixError


class MixClient:
    log: logging.Logger = logging.getLogger("mau.mix.client")
    loop: asyncio.AbstractEventLoop
    unix: bool
    host: str
    port: int
    conn_id: int
    conn_name: str
    http_address: str
    _handler: ConnectionHandler
    _writer: asyncio.StreamWriter
    _reader: asyncio.StreamReader

    def __init__(self, address: str, conn_id: int, conn_name: str, http_address: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        if address.startswith("tcp://"):
            self.unix = False
            addr = address[len("tcp://"):].split(":", 1)
            self.host = addr[0]
            if len(addr) > 1:
                try:
                    self.port = int(addr[1])
                except ValueError as e:
                    raise ValueError("Invalid port") from e
        elif address.startswith("unix://"):
            self.unix = True
            self.host = address[len("unix://"):]
        else:
            raise ValueError("Unknown protocol")
        self.conn_id = conn_id
        self.conn_name = conn_name
        self.http_address = http_address
        self.loop = loop or asyncio.get_event_loop()

    @property
    def address(self) -> str:
        if self.unix:
            return f"unix://{self.unix}"
        else:
            return f"tcp://{self.host}:{self.port}"

    async def _open_connection(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self.unix:
            return await asyncio.open_unix_connection(self.host, loop=self.loop)
        else:
            return await asyncio.open_connection(self.host, self.port, loop=self.loop)

    async def connect(self) -> None:
        self.log.debug("Connecting to mix server...")
        while True:
            try:
                r, w = await self._open_connection()
            except ConnectionRefusedError:
                self.log.exception(f"Connection to mix server failed, retrying in 10 seconds")
                await asyncio.sleep(10)
                continue
            self._handler = ConnectionHandler(r, w, id=self.conn_id, name=self.conn_name,
                                              http_address=self.http_address, is_server=False,
                                              log=self.log, loop=self.loop)
            self.log.debug("Connection OK, sending init command...")
            try:
                payload = f"{self.conn_id};{self.conn_name};{self.http_address}".encode("utf-8")
                await self._handler.call(Command.CONNECT, payload,
                                         expected_response=(Response.CONNECT_OK,))
                break
            except asyncio.TimeoutError:
                self.log.exception(f"Timeout sending init to mix server, retrying in 10 seconds")
            except MixError:
                self.log.exception(f"Error while sending init to server, retrying in 10 seconds")
            await self._handler.disconnect()
            await asyncio.sleep(10)
        self.log.info(f"Successfully connected to mix server at {self.address}")

    def call(self, cmd: Command, payload: bytes,
             expected_response: Optional[Tuple[Response, ...]] = None
             ) -> Awaitable[Tuple[Response, bytes]]:
        return self._handler.call(cmd, payload, expected_response=expected_response)

    def listen(self) -> None:
        self._handler.start()

    def stop_listen(self) -> None:
        self._handler.stop()
