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
from typing import Tuple
from enum import IntEnum
import asyncio
import struct


class Command(IntEnum):
    UNKNOWN = 0
    QUIT = 1
    LOCK = 2
    UNLOCK = 3
    CACHE_UPDATE = 4


class Response(IntEnum):
    LOCKED = 1
    ERROR = 2


# Header: request ID (int32), command/response code (int8), payload length (int32)
proto_header = "!IBI"
proto_header_len = 9


async def write_response(writer: asyncio.StreamWriter, req_id: int, resp: Response,
                         payload: bytes) -> None:
    writer.write(struct.pack(proto_header, req_id, resp, len(payload)))
    writer.write(payload)
    await writer.drain()


async def read_command(reader: asyncio.StreamReader) -> Tuple[int, Command, bytes]:
    req_id, cmd, length = struct.unpack(proto_header, await reader.readexactly(7))
    payload = await reader.readexactly(length)
    try:
        cmd = Command(cmd)
    except ValueError:
        cmd = Command.UNKNOWN
    return req_id, cmd, payload
