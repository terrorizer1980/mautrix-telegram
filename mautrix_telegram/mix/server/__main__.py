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
import argparse
import logging
import asyncio
import sys

from ..protocol import Command, Response, write, read
from .handlers import commands

parser = argparse.ArgumentParser(description="Mixing server for multiprocess mautrix-telegram.",
                                 prog="python -m mautrix_telegram.mix.server")
parser.add_argument("-h", "--host", type=str, default="127.0.0.1", metavar="<ip>",
                    help="The IP address to listen on")
parser.add_argument("-p", "--port", type=str, default="29323", metavar="<port>",
                    help="The port to listen on")
parser.add_argument("-u", "--unix", action="store_true",
                    help="Create an Unix socket instead of TCP")
args = parser.parse_args()

log = logging.getLogger("mau.mix.server")


async def handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        req_id, cmd, payload = await read(reader)
    except asyncio.IncompleteReadError:
        writer.close()
        return
    if cmd != Command.CONNECT or req_id != 0:
        await write(writer, req_id, Response.ERROR, b"expected connect command")
        writer.close()
        return
    conn_id, conn_name = payload.decode("utf-8").split(";")
    conn_log = log.getChild(conn_id)
    conn_log.info(f"{conn_name} connected")

    running_handlers: Dict[int, asyncio.Future] = {}

    async def handle_command(req_id: int, cmd: Command, payload: bytes) -> None:
        try:
            return_val = await commands[cmd](payload)
            if isinstance(return_val, Response):
                resp = return_val
                data = b""
            else:
                resp, data = return_val
            await write(writer, req_id, resp, data)
        except Exception:
            conn_log.exception("Error in command handler")
            await write(writer, req_id, Response.ERROR, b"internal error")
        try:
            del running_handlers[req_id]
        except KeyError:
            pass

    while True:
        try:
            req_id, cmd, payload = await read(reader)
        except asyncio.IncompleteReadError:
            conn_log.warning("Incomplete read, disconnecting...")
            break
        if cmd == Command.QUIT:
            conn_log.info(f"Received QUIT, disconnecting...")
            break
        conn_log.debug(f"Received request #{req_id}: {cmd.name}")
        task = asyncio.ensure_future(handle_command(req_id, cmd, payload))
        if req_id != 0:
            running_handlers[req_id] = task

    for handler in running_handlers.values():
        handler.cancel()
    try:
        writer.write_eof()
        await writer.drain()
    except Exception:
        pass
    writer.close()
    if sys.version_info >= (3, 7):
        await writer.wait_closed()
    conn_log.info(f"{conn_name} disconnected")


loop = asyncio.get_event_loop()

if args.unix:
    server_creator = asyncio.start_unix_server(handle_conn, args.host, loop=loop)
    listen_addr = f"unix://{args.host}"
else:
    server_creator = asyncio.start_server(handle_conn, args.host, args.port, loop=loop)
    listen_addr = f"tcp://{args.host}:{args.port}"
server = loop.run_until_complete(server_creator)
log.info(f"Listening at {listen_addr}")
try:
    loop.run_forever()
except KeyboardInterrupt:
    server.close()
    loop.run_until_complete(server.wait_closed())
except Exception:
    log.fatal("Fatal error in server", exc_info=True)
    sys.exit(10)
loop.close()
