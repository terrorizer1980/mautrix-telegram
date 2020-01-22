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

from aiohttp import web, ClientSession

from .conns import conn_manager


# TODO make this less hacky
async def start_aiohttp():
    sess = ClientSession()

    async def mux_txn(req: web.Request) -> web.Response:
        await asyncio.gather(*[sess.put(
            url=(conn.http_address / "transactions" / req.match_info["txnid"]).with_query({
                "access_token": req.rel_url.query["access_token"],
            }),
            data=await req.read(),
        ) for conn in conn_manager.values()])
        return web.json_response({})

    app = web.Application()
    app.router.add_route("PUT", "/transactions/{txnid}", mux_txn)
    app.router.add_route("PUT", "/_matrix/app/v1/transactions/{txnid}", mux_txn)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.2.3', 29317)
    await site.start()
