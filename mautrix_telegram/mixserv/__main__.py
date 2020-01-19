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
from typing import Dict, Callable, Awaitable, Tuple, Optional
import argparse
import logging
import asyncio
import sys

from .protocol import Command, Response, write_response, read_command

parser = argparse.ArgumentParser(description="Mixing server for multiprocess mautrix-telegram.",
                                 prog="python -m mautrix_telegram.mixserv")
parser.add_argument("-h", "--host", type=str, default="127.0.0.1", metavar="<ip>",
                    help="The IP address to listen on")
parser.add_argument("-p", "--port", type=str, default="29323", metavar="<port>",
                    help="The port to listen on")
parser.add_argument("-u", "--unix", action="store_true",
                    help="Create an Unix socket instead of TCP")
args = parser.parse_args()

log = logging.getLogger(__name__)

HandlerReturn = Tuple[Response, bytes]
Handler = Callable[[bytes], Awaitable[HandlerReturn]]


async def unknown_command(_: bytes) -> HandlerReturn:
    return Response.ERROR, b"unknown command"


commands: Dict[Command, Handler] = {
    Command.UNKNOWN: unknown_command
}


async def handle_conn(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    running_handlers: Dict[int, asyncio.Future] = {}

    async def handle_command(req_id: int, cmd: Command, payload: bytes) -> None:
        try:
            resp, data = await commands[cmd](payload)
            await write_response(writer, req_id, resp, data)
        except Exception:
            log.exception("Error in command handler")
            await write_response(writer, req_id, Response.ERROR, b"internal error")
        try:
            del running_handlers[req_id]
        except KeyError:
            pass

    while True:
        req_id, cmd, payload = await read_command(reader)
        if cmd == Command.QUIT:
            break
        running_handlers[req_id] = asyncio.ensure_future(handle_command(req_id, cmd, payload))

    for handler in running_handlers.values():
        handler.cancel()
    writer.write_eof()
    await writer.drain()
    writer.close()
    # PY3.7 only
    # await writer.wait_closed()


loop = asyncio.get_event_loop()
server: Optional[asyncio.Server] = None


async def main():
    global server
    if args.unix:
        server = await asyncio.start_unix_server(handle_conn, args.host, loop=loop)
    else:
        server = await asyncio.start_server(handle_conn, args.host, args.port, loop=loop)


loop.run_until_complete(main())
try:
    loop.run_forever()
except KeyboardInterrupt:
    server.close()
    loop.run_until_complete(server.wait_closed())
except Exception:
    log.fatal("Fatal error in server", exc_info=True)
    sys.exit(10)
loop.close()
