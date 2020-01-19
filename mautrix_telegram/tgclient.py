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
from typing import List, Union, Optional

from telethon import TelegramClient, utils
from telethon.tl.functions import InvokeWithoutUpdatesRequest
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.types import (InputMediaUploadedDocument, InputMediaUploadedPhoto,
                               TypeDocumentAttribute, TypeInputMedia, TypeInputPeer,
                               TypeMessageEntity, TypeMessageMedia, TypePeer)
from telethon.tl.patched import Message
from telethon.sessions.abstract import Session


class MautrixTelegramClient(TelegramClient):
    session: Session
    no_updates: bool = False

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

    def __call__(self, request, ordered=False):
        if self.no_updates and not isinstance(request, InvokeWithoutUpdatesRequest):
            request = InvokeWithoutUpdatesRequest(request)
        return super().__call__(request, ordered)

    async def connect(self) -> None:
        if not await self._sender.connect(self._connection(
            self.session.server_address,
            self.session.port,
            self.session.dc_id,
            loop=self._loop,
            loggers=self._log,
            proxy=self._proxy
        )):
            # We don't want to init or modify anything if we were already connected
            return

        self.session.auth_key = self._sender.auth_key
        self.session.save()

        await self._sender.send(self._init_with(GetConfigRequest()))

        if not self.no_updates:
            self._updates_handle = self._loop.create_task(self._update_loop())
