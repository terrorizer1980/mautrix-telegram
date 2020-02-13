# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2019 Tulir Asokan
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
from typing import Any, Tuple, Dict

from telethon.tl import TLRequest

from .mix import Command
from .mix.client import MixClient


class ProxyTelegramClient:
    mix: MixClient
    mxid: str
    target_bucket: int
    in_bucket: bool = False
    proxyable_methods: Tuple[str, ...] = ("is_user_authorized", "get_me", "get_input_entity",
                                          "get_entity", "sign_in", "sign_up", "log_out",
                                          "send_message", "send_read_acknowledge",
                                          "kick_participant", "edit_permissions", "edit_admin",
                                          "delete_dialog", "delete_messages", "get_messages")
    _created_proxies: Dict[str, Any]

    def __init__(self, mix: MixClient, mxid: str, target_bucket: int) -> None:
        self.mix = mix
        self.mxid = mxid
        self.target_bucket = target_bucket
        self._created_proxies = {}

    async def __call__(self, request: TLRequest) -> Any:
        return await self.mix.pickled_call(Command.TELEGRAM_RPC, target=self.target_bucket,
                                           payload=(self.mxid, request))

    @staticmethod
    def is_connected() -> bool:
        return True

    def __getattr__(self, item: str) -> Any:
        if item not in self.proxyable_methods:
            raise KeyError(item)

        try:
            return self._created_proxies[item]
        except KeyError:
            async def proxy(*args, **kwargs) -> Any:
                return await self.mix.pickled_call(Command.TELEGRAM_RPC, target=self.target_bucket,
                                                   payload=(self.mxid, (item, args, kwargs)))

            self._created_proxies[item] = proxy
            return proxy
