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
from typing import Dict, Deque, Tuple, Optional
from collections import defaultdict, deque

from mautrix.types import RoomID, EventID

from ...types import TelegramID
from ..protocol import Command, Response
from ..handlers import register_handler, HandlerReturn, ConnectionHandler

DedupMXID = Tuple[EventID, TelegramID]
cache_queue_length: int = 20

dedup: Dict[RoomID, Deque[str]] = defaultdict(lambda: deque())
dedup_mxid: Dict[RoomID, Dict[str, DedupMXID]] = defaultdict(lambda: {})
dedup_action: Dict[RoomID, Deque[str]] = defaultdict(lambda: deque())


@register_handler(Command.DEDUP_CHECK_ACTION)
async def check_action(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    room_id, evt_hash = payload.decode("utf-8").split(";")
    local_data = dedup_action[room_id]
    if evt_hash in local_data:
        return Response.DEDUP_FOUND
    local_data.append(evt_hash)
    if len(local_data) > cache_queue_length:
        local_data.popleft()
    return Response.DEDUP_NOT_FOUND


def str_to_dedup_mxid(val: str) -> Optional[DedupMXID]:
    if not val:
        return None
    mxid, tgid = val.rsplit(":", 1)
    return EventID(mxid), TelegramID(int(tgid))


def dedup_mxid_to_bytes(mxid: DedupMXID) -> bytes:
    return b":".join(str(val).encode("utf-8") for val in mxid)


@register_handler(Command.DEDUP_UPDATE)
async def update(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    room_id, evt_hash, mxid, expected_mxid = payload.decode("utf-8").split(";")
    mxid = str_to_dedup_mxid(mxid)
    expected_mxid = str_to_dedup_mxid(expected_mxid)
    local_mxid_data = dedup_mxid[room_id]
    try:
        found_mxid = local_mxid_data[evt_hash]
    except KeyError:
        return Response.DEDUP_FOUND, b"None:0"

    if found_mxid != expected_mxid:
        return Response.DEDUP_FOUND, dedup_mxid_to_bytes(found_mxid)

    local_mxid_data[evt_hash] = mxid
    return Response.DEDUP_NOT_FOUND


@register_handler(Command.DEDUP_CHECK_MESSAGE)
async def on_unlock(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    room_id, evt_hash, mxid = payload.decode("utf-8").split(";")
    mxid = str_to_dedup_mxid(mxid)
    local_mxid_data = dedup_mxid[room_id]
    local_data = dedup[room_id]
    if evt_hash in local_data:
        return Response.DEDUP_FOUND, dedup_mxid_to_bytes(local_mxid_data[evt_hash])

    local_mxid_data[evt_hash] = mxid
    local_data.append(evt_hash)
    if len(local_data) > cache_queue_length:
        del local_mxid_data[local_data.popleft()]

    return Response.DEDUP_NOT_FOUND
