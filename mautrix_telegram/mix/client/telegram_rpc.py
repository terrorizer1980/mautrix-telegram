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
import pickle

from ... import user as u
from ..handlers import register_handler, Command, Response, HandlerReturn, ConnectionHandler


@register_handler(Command.TELEGRAM_RPC)
async def telegram_rpc(_: ConnectionHandler, payload: bytes) -> HandlerReturn:
    user_id, request = pickle.loads(payload)
    if user_id == "bot":
        user = u.User.relaybot
    else:
        user = u.User.get_by_mxid(user_id, create=False)
    if not user or not user.in_bucket:
        return Response.ERROR, b"user not in this bucket"
    try:
        resp = await user.client(request)
    except Exception as e:
        return Response.TELEGRAM_RPC_ERROR, pickle.dumps(e)
    return Response.TELEGRAM_RPC_OK, pickle.dumps(resp)
