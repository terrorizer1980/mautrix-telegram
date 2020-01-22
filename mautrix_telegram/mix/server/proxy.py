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
import asyncio
import struct
import pickle

from ..protocol import Command, Response
from ..handlers import ConnectionHandler, register_handler, HandlerReturn
from .conns import conn_manager


proxy_header = "!Ib"
proxy_header_len = struct.calcsize(proxy_header)


@register_handler(Command.PROXY)
async def proxy(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    if len(payload) < proxy_header_len:
        return Response.ERROR, b"bad request"
    target, cmd = struct.unpack(proxy_header, payload[:proxy_header_len])
    payload = payload[proxy_header_len:]
    try:
        cmd = Command(cmd)
    except ValueError:
        return Response.ERROR, b"invalid command to proxy"
    try:
        conn = conn_manager.conns[target]
    except KeyError:
        return Response.ERROR, b"proxy target connection not found"
    return await conn.call(cmd, payload, throw_error=False)


broadcast_header = "!b?"
broadcast_header_len = struct.calcsize(broadcast_header)


@register_handler(Command.BROADCAST)
async def broadcast(self: ConnectionHandler, payload: bytes) -> HandlerReturn:
    if len(payload) < broadcast_header_len:
        return Response.ERROR, b"bad request"
    cmd, to_self = struct.unpack(broadcast_header, payload[:broadcast_header_len])
    payload = payload[broadcast_header_len:]
    try:
        cmd = Command(cmd)
    except ValueError:
        return Response.ERROR, b"invalid command to broadcast"
    conns = [conn for conn in conn_manager.conns.values() if conn != self or to_self]
    conn_ids = [conn.id for conn in conns]
    resps = await asyncio.gather(*[conn.call(cmd, payload, throw_error=False)
                                   for conn in conns])
    data = {conn_id: (resp, payload) for conn_id, (resp, payload) in zip(conn_ids, resps)}
    return Response.BROADCAST_RESPONSES, pickle.dumps(data)
