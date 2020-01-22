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
from typing import Dict
import asyncio

from ..protocol import Command, Response
from ..handlers import register_handler, HandlerReturn, ConnectionHandler

locks: Dict[bytes, asyncio.Lock] = {}


@register_handler(Command.LOCK)
async def on_lock(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    try:
        lock = locks[payload]
    except KeyError:
        lock = locks[payload] = asyncio.Lock()
    await lock.acquire()
    return Response.LOCKED


@register_handler(Command.OPTIONAL_LOCK)
async def on_optional_lock(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    try:
        await locks[payload].acquire()
        return Response.LOCKED
    except KeyError:
        return Response.LOCK_NOT_FOUND


@register_handler(Command.UNLOCK)
async def on_unlock(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    locks[payload].release()
    return Response.UNLOCKED
