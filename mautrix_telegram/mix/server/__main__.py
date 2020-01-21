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
import logging.config
import argparse
import asyncio
import sys

from ruamel.yaml import YAML
from yarl import URL

from ..protocol import Command, Response, write, read
from ..handlers import ConnectionHandler, register_handler, HandlerReturn
from . import locks

parser = argparse.ArgumentParser(description="Mixing server for multiprocess mautrix-telegram.",
                                 prog="python -m mautrix_telegram.mix.server")
parser.add_argument("-i", "--ip", type=str, default="127.0.0.1", metavar="<ip>",
                    help="The IP address or hostname to listen on")
parser.add_argument("-p", "--port", type=int, default=29323, metavar="<port>",
                    help="The port to listen on")
parser.add_argument("-u", "--unix", type=str, default="", metavar="<path>",
                    help="Create an Unix socket instead of TCP")
parser.add_argument("-l", "--log-config", type=str, default="", metavar="<path>",
                    help="Path to a YAML-formatted Python log config")
args = parser.parse_args()

if args.log_config:
    with open(args.log_config, "r") as file:
        logging.config.dictConfig(YAML().load(file))
log = logging.getLogger("mau.mix")


@register_handler(Command.CONNECT)
async def already_connected(_: bytes) -> HandlerReturn:
    return Response.ERROR, b"received duplicate connect command"


conns: Dict[str, ConnectionHandler] = {}


async def handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        req_id, cmd, payload = await read(reader)
    except asyncio.IncompleteReadError:
        writer.close()
        return
    if cmd != Command.CONNECT:
        await write(writer, req_id, Response.ERROR, b"expected connect command")
        writer.close()
        return
    conn_id, http_address = payload.decode("utf-8").split(";")
    conn_log = log.getChild(conn_id)
    if conn_id in conns:
        conn_log.warning("Existing connection found, stopping...")
        conns[conn_id].stop()
    handler = ConnectionHandler(reader, writer, is_server=True, log=conn_log, loop=loop)
    handler.http_address = URL(http_address)
    conns[conn_id] = handler
    await write(writer, req_id, Response.CONNECT_OK, b"foo")
    conn_log.info(f"{conn_id} connected from {handler.ip}")
    await handler.run()
    try:
        if conns[conn_id] == handler:
            del conns[conn_id]
    except KeyError:
        pass
    conn_log.info(f"{conn_id} disconnected")


async def try_handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        await handle_conn(reader, writer)
    except Exception:
        sock = writer.transport.get_extra_info("socket")
        ip = ":".join(str(part) for part in sock.getpeername())
        log.exception(f"Fatal error in {ip} connection handler")
        writer.close()


async def close_conns() -> None:
    log.debug("Disconnecting connections...")
    await asyncio.gather(*[conn.call(Command.QUIT, no_response=True) for conn in conns.values()])
    await asyncio.gather(*[conn.disconnect() for conn in conns.values()])


async def start_aiohttp():
    from aiohttp import web, ClientSession

    sess = ClientSession()

    async def mux_txn(req: web.Request) -> web.Response:
        await asyncio.gather(*[sess.put(
            url=(conn.http_address / "transactions" / req.match_info["txnid"]).with_query({
                "access_token": req.rel_url.query["access_token"],
            }),
            data=await req.read(),
        ) for conn in conns.values()])
        return web.json_response({})

    app = web.Application()
    app.router.add_route("PUT", "/transactions/{txnid}", mux_txn)
    app.router.add_route("PUT", "/_matrix/app/v1/transactions/{txnid}", mux_txn)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.2.3', 29317)
    await site.start()


loop = asyncio.get_event_loop()

if args.unix:
    server_creator = asyncio.start_unix_server(try_handle_conn, args.unix, loop=loop)
    listen_addr = f"unix://{args.unix}"
else:
    server_creator = asyncio.start_server(try_handle_conn, args.ip, args.port, loop=loop)
    listen_addr = f"tcp://{args.ip}:{args.port}"
log.debug("Starting server...")
server = loop.run_until_complete(server_creator)
log.info(f"Listening at {listen_addr}")
loop.run_until_complete(start_aiohttp())
try:
    loop.run_forever()
except KeyboardInterrupt:
    log.debug("Interrupt received, stopping...")
    loop.run_until_complete(close_conns())
    server.close()
    loop.run_until_complete(server.wait_closed())
except Exception:
    log.fatal("Fatal error in server", exc_info=True)
    sys.exit(10)
loop.close()
