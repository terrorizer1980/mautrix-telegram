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
from typing import Dict, Callable, Awaitable, Tuple, Union

from ..protocol import Response, Command

HandlerReturn = Union[Tuple[Response, bytes], Response]
Handler = Callable[[bytes], Awaitable[HandlerReturn]]

commands: Dict[Command, Handler] = {}


def register_handler(cmd: Command) -> Callable[[Handler], Handler]:
    def wrapper(fn: Handler) -> Handler:
        commands[cmd] = fn
        return fn

    return wrapper


@register_handler(Command.UNKNOWN)
async def unknown_command(_: bytes) -> HandlerReturn:
    return Response.ERROR, b"unknown command"


@register_handler(Command.CONNECT)
async def already_connected(_: bytes) -> HandlerReturn:
    return Response.ERROR, b"received duplicate connect command"
