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
import logging.config
import argparse
import asyncio
import sys

from ruamel.yaml import YAML

from ..protocol import Command, Response
from ..handlers import ConnectionHandler, register_handler, HandlerReturn
from .conns import conn_manager
from . import locks, proxy, txn_mux

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


@register_handler(Command.CONNECT)
async def already_connected(_1: ConnectionHandler, _2: bytes) -> HandlerReturn:
    return Response.ERROR, b"received duplicate connect command"


if args.log_config:
    with open(args.log_config, "r") as file:
        logging.config.dictConfig(YAML().load(file))
log = logging.getLogger("mau.mix.init")

loop = asyncio.get_event_loop()

if args.unix:
    server_creator = asyncio.start_unix_server(conn_manager, args.unix, loop=loop)
    listen_addr = f"unix://{args.unix}"
else:
    server_creator = asyncio.start_server(conn_manager, args.ip, args.port, loop=loop)
    listen_addr = f"tcp://{args.ip}:{args.port}"
log.debug("Starting server...")
server = loop.run_until_complete(server_creator)
log.info(f"Listening at {listen_addr}")
loop.run_until_complete(txn_mux.start_aiohttp())
try:
    loop.run_forever()
except KeyboardInterrupt:
    log.debug("Interrupt received, stopping...")
    loop.run_until_complete(conn_manager.close_all())
    server.close()
    loop.run_until_complete(server.wait_closed())
except Exception:
    log.fatal("Fatal error in server", exc_info=True)
    sys.exit(10)
loop.close()
