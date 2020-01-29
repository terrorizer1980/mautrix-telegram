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
from typing import List, Union, Optional, Awaitable
import pickle

from telethon import TelegramClient, utils
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import (InputMediaUploadedDocument, InputMediaUploadedPhoto,
                               TypeDocumentAttribute, TypeInputMedia, TypeInputPeer,
                               TypeMessageEntity, TypeMessageMedia, TypePeer)
from telethon.tl.patched import Message
from telethon.sessions.abstract import Session

from .mix.client import MixClient
from .mix import Command, Response


class MautrixTelegramClient(TelegramClient):
    session: Session
    no_updates: bool = False
    mix: MixClient
    mxid: str
    target_bucket: int

    async def upload_file_direct(self, file: bytes, mime_type: str = None,
                                 attributes: List[TypeDocumentAttribute] = None,
                                 file_name: str = None, max_image_size: float = 10 * 1000 ** 2,
                                 ) -> Union[InputMediaUploadedDocument, InputMediaUploadedPhoto]:
        file_handle = await super().upload_file(file, file_name=file_name)

        if (mime_type == "image/png" or mime_type == "image/jpeg") and len(file) < max_image_size:
            return InputMediaUploadedPhoto(file_handle)
        else:
            attributes = attributes or []
            attr_dict = {type(attr): attr for attr in attributes}

            return InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type or "application/octet-stream",
                attributes=list(attr_dict.values()))

    async def send_media(self, entity: Union[TypeInputPeer, TypePeer],
                         media: Union[TypeInputMedia, TypeMessageMedia],
                         caption: str = None, entities: List[TypeMessageEntity] = None,
                         reply_to: int = None) -> Optional[Message]:
        entity = await self.get_input_entity(entity)
        reply_to = utils.get_message_id(reply_to)
        request = SendMediaRequest(entity, media, message=caption or "", entities=entities or [],
                                   reply_to_msg_id=reply_to)
        return self._get_response_message(request, await self(request), entity)

    async def __call__(self, request, ordered=False):
        if self.no_updates:
            print(f"Proxying {request} through {self.target_bucket}")
            req = pickle.dumps((self.mxid, request))
            code, data = await self.mix.call(Command.TELEGRAM_RPC, req, proxy=self.target_bucket,
                                             expected_response=(Response.TELEGRAM_RPC_OK,
                                                                Response.TELEGRAM_RPC_ERROR))
            resp = pickle.loads(data)
            if code == Response.TELEGRAM_RPC_ERROR:
                raise resp
            else:
                return resp
        else:
            return await super().__call__(request, ordered)

    def connect(self) -> Awaitable[None]:
        if self.no_updates:
            raise ValueError("Can't connect() delegated client")
        return super().connect()
