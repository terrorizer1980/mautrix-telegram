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
from typing import Tuple, Dict, Any, Optional

from telethon.tl import TLRequest, TLObject
from telethon.tl.types import TypeInputFile
from telethon.errors import RPCError

from mautrix.types import UserID, MediaMessageEventContent, MessageType
from mautrix.appservice import IntentAPI

from ... import user as u
from ...db import TelegramFile as DBTelegramFile
from ...util import transfer_file_to_matrix, parallel_transfer_to_telegram, convert_image
from ..handlers import register_handler, register_pickled_handler, Command, Response, ErrorResponse


def get_user(user_id: UserID) -> 'u.User':
    if user_id == "bot":
        user = u.User.relaybot
    else:
        user = u.User.get_by_mxid(user_id, create=False)
    if not user or not user.in_bucket:
        raise ErrorResponse(b"user not in this bucket")
    return user


def get_intent(user_id: UserID) -> IntentAPI:
    az = u.User.ctx.az
    return az.intent if user_id == az.bot_mxid else az.intent.user(user_id)


@register_pickled_handler(Command.TELEGRAM_ENSURE_STARTED)
async def ensure_started(data: Tuple[UserID, bool]) -> None:
    user_id, even_if_no_session = data
    await get_user(user_id).ensure_started(even_if_no_session)


@register_pickled_handler(Command.TELEGRAM_RPC)
async def telegram_rpc(data: Tuple[UserID, TLRequest]) -> TLObject:
    user_id, request = data
    user = await get_user(user_id).ensure_started()
    if not user.client:
        raise RPCError(request, "Client not created")
    return await user.client(request)


@register_pickled_handler(Command.FILE_TRANSFER_TO_MATRIX)
async def rpc_transfer_file_to_matrix(data: Dict[str, Any]) -> Optional[DBTelegramFile]:
    user = await get_user(data.pop("client")).ensure_started()
    if not user.client:
        raise RPCError(None, "Client not created")
    intent = get_intent(data.pop("intent"))
    return await transfer_file_to_matrix(client=user.client, intent=intent, **data)


@register_pickled_handler(Command.FILE_TRANSFER_TO_TELEGRAM)
async def rpc_transfer_file_to_telegram(data: Tuple[UserID, UserID, MediaMessageEventContent, int]
                                        ) -> Tuple[TypeInputFile, int, Optional[Tuple[Any, ...]]]:
    client_mxid, intent_mxid, content, parallel_id = data
    mxc_url = content if isinstance(content, str) else content.url
    user = await get_user(client_mxid).ensure_started()
    if not user.client:
        raise RPCError(None, "Client not created")
    client = user.client
    intent = get_intent(intent_mxid)
    if parallel_id:
        handle, size = await parallel_transfer_to_telegram(client, intent, mxc_url, parallel_id)
        data = None
    else:
        file = await intent.download_media(mxc_url)
        file_name = mime = w = h = None

        if getattr(content, "msgtype") == MessageType.STICKER:
            if content.info.mimetype != "image/gif":
                mime, file, w, h = convert_image(file, source_mime=content.info.mimetype,
                                                      target_type="webp")
            else:
                # Remove sticker description
                file_name = "sticker.gif"

        handle = await client.upload_file(file)
        size = len(file)
        data = (mime, file_name, w, h)
    return handle, size, data
