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
from typing import Tuple, Union
from enum import IntEnum
import asyncio
import struct


class Command(IntEnum):
    UNKNOWN = 0
    CONNECT = 1
    QUIT = 2
    LOCK = 3
    OPTIONAL_LOCK = 4
    UNLOCK = 5
    PROXY = 7
    BROADCAST = 8
    UPDATE_CACHE = 9
    TELEGRAM_RPC = 10


class Response(IntEnum):
    UNKNOWN = -1
    CONNECT_OK = -2
    ERROR = -3
    LOCKED = -4
    LOCK_NOT_FOUND = -5
    UNLOCKED = -6
    BROADCAST_RESPONSES = -7
    TELEGRAM_RPC_OK = -8
    TELEGRAM_RPC_ERROR = -9


# Header: request ID (int32), action code (int8), payload length (uint32)
_header = "!ibI"
_header_len = struct.calcsize(_header)

# Proxy header: target conn_id (int32), action code (int8)
proxy_header = "!Ib"
proxy_header_len = struct.calcsize(proxy_header)

# Proxy header: action code (int8), echo (bool)
broadcast_header = "!b?"
broadcast_header_len = struct.calcsize(broadcast_header)


async def write(writer: asyncio.StreamWriter, req_id: int, action: Union[Response, Command],
                payload: bytes = b"") -> None:
    # TODO remove debug print
    print("-->", req_id, action.name, payload)
    writer.write(struct.pack(_header, req_id, action, len(payload)))
    writer.write(payload)
    await writer.drain()


async def read(reader: asyncio.StreamReader) -> Tuple[int, Union[Command, Response], bytes]:
    req_id, action, length = struct.unpack(_header, await reader.readexactly(_header_len))
    payload = await reader.readexactly(length)
    if action < 0:
        try:
            action = Response(action)
        except ValueError:
            action = Response.UNKNOWN
    else:
        try:
            action = Command(action)
        except ValueError:
            action = Command.UNKNOWN
    # TODO remove debug print
    print("<--", req_id, action.name, payload)
    return req_id, action, payload
