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
from ..protocol import Command, Response
from .client import MixClient


class MixLock:
    client: MixClient
    key: bytes
    required: bool
    locked: bool

    def __init__(self, client: MixClient, key: bytes, required: bool = True) -> None:
        self.client = client
        self.key = key
        self.required = required
        self.locked = False

    async def __aenter__(self) -> None:
        if self.required:
            resp, payload = await self.client.call(Command.LOCK, self.key,
                                                   expected_response=(Response.LOCKED,))
        else:
            resp, payload = await self.client.call(Command.OPTIONAL_LOCK, self.key,
                                                   expected_response=(Response.LOCKED,
                                                                      Response.LOCK_NOT_FOUND))
        self.locked = resp == Response.LOCKED

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if not self.locked:
            return
        await self.client.call(Command.UNLOCK, self.key)
