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
from typing import Dict, Tuple, Optional
import logging.config
import asyncio

from ..protocol import Command, Response, write, read
from ..handlers import ConnectionHandler


class ConnectionManager:
    log: logging.Logger = logging.getLogger("mau.mix")
    loop: asyncio.AbstractEventLoop
    conns: Dict[int, ConnectionHandler]

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.conns = {}
        self.loop = loop or asyncio.get_event_loop()

    @staticmethod
    async def _parse_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter
                             ) -> Optional[Tuple[int, int, str, str]]:
        try:
            req_id, cmd, payload = await read(reader)
        except asyncio.IncompleteReadError:
            writer.close()
            return None
        if cmd != Command.CONNECT:
            await write(writer, req_id, Response.ERROR, b"expected connect command")
            return None
        try:
            conn_id, conn_name, http_address = payload.decode("utf-8").split(";")
        except UnicodeDecodeError:
            await write(writer, req_id, Response.ERROR, b"invalid connect payload: not unicode")
            return None
        except ValueError:
            await write(writer, req_id, Response.ERROR,
                        b"invalid connect payload: part count != 3")
            return None
        try:
            conn_id = int(conn_id)
        except ValueError:
            await write(writer, req_id, Response.ERROR,
                        b"invalid connect payload: connection ID not int")
        return req_id, conn_id, conn_name, http_address

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connect_cmd = await self._parse_connect(reader, writer)
        if not connect_cmd:
            writer.close()
            return
        connect_req_id, conn_id, conn_name, http_address = connect_cmd
        conn_log = self.log.getChild(conn_name)
        if conn_id in self.conns:
            conn_log.warning("Existing connection found, stopping...")
            self.conns[conn_id].stop()
        handler = ConnectionHandler(reader, writer, id=conn_id, name=conn_name, log=conn_log,
                                    http_address=http_address, is_server=True, loop=self.loop)
        self.conns[conn_id] = handler
        await write(writer, connect_req_id, Response.CONNECT_OK, b"")
        conn_log.info(f"{conn_name} (ID {conn_id}) connected from {handler.ip}")
        await handler.run()
        try:
            if self.conns[conn_id] == handler:
                del self.conns[conn_id]
        except KeyError:
            pass
        conn_log.info(f"{conn_name} (ID {conn_id}) disconnected")

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except Exception:
            try:
                sock = writer.transport.get_extra_info("socket")
                ip = ":".join(str(part) for part in sock.getpeername())
            except Exception:
                ip = "<unknown ip>"
            self.log.exception(f"Fatal error in {ip} connection handler")
            writer.close()

    async def close_all(self) -> None:
        self.log.debug("Disconnecting connections...")
        await asyncio.gather(*[conn.call(Command.QUIT, no_response=True)
                               for conn in self.conns.values()])
        await asyncio.gather(*[conn.disconnect() for conn in self.conns.values()])


conn_manager = ConnectionManager()
