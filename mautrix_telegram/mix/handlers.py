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
from typing import Dict, Callable, Awaitable, Any, Tuple, Union, Optional
import functools
import traceback
import asyncio
import logging
import pickle
import sys

from yarl import URL

from .protocol import Response, Command, read, write
from .errors import ErrorResponse, MixError, UnexpectedResponse

HandlerReturn = Union[Tuple[Response, bytes], Response]
Handler = Callable[['ConnectionHandler', bytes], Awaitable[HandlerReturn]]
PickleHandler = Callable[[Any], Awaitable[Any]]

commands: Dict[Command, Handler] = {}

log = logging.getLogger("mau.mix.picklerror")


def register_pickled_handler(cmd: Command) -> Callable[[PickleHandler], Handler]:
    def wrapper(fn: PickleHandler) -> Handler:
        @functools.wraps(fn)
        async def wrap(_: 'ConnectionHandler', payload: bytes) -> HandlerReturn:
            data = pickle.loads(payload)
            try:
                return Response.PICKLED_OK, pickle.dumps(await fn(data))
            except MixError as e:
                return e.response, e.payload
            except Exception as e:
                log.exception(f"Error handling {cmd.name}")
                return Response.PICKLED_ERROR, pickle.dumps(e)

        commands[cmd] = wrap
        return wrap

    return wrapper


def register_handler(cmd: Command) -> Callable[[Handler], Handler]:
    def wrapper(fn: Handler) -> Handler:
        commands[cmd] = fn
        return fn

    return wrapper


@register_handler(Command.UNKNOWN)
async def unknown_command(_1: 'ConnectionHandler', _2: bytes) -> HandlerReturn:
    return Response.ERROR, b"unknown command"


class ConnectionHandler:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    _log: logging.Logger
    _loop: asyncio.AbstractEventLoop
    _ongoing_commands: Dict[int, asyncio.Future]
    _req_id: int
    _listen_task: Optional[asyncio.Task]
    _is_listening: bool
    is_server: bool

    id: int
    name: str
    http_address: URL

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 id: int, name: str, http_address: str, is_server: bool,
                 log: Optional[logging.Logger] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._reader = reader
        self._writer = writer
        self.is_server = is_server
        self._log = log or logging.getLogger("mau.mix.connection")
        self._loop = loop or asyncio.get_event_loop()
        self._ongoing_commands = {}
        self._req_id = 0
        self._listen_task = None
        self._is_listening = False
        self.id = id
        self.name = name
        self.http_address = URL(http_address)

    @property
    def ip(self) -> str:
        sock = self._writer.transport.get_extra_info("socket")
        return ":".join(str(part) for part in sock.getpeername())

    @property
    def next_req_id(self) -> int:
        self._req_id += -1 if self.is_server else +1
        return self._req_id

    async def call(self, cmd: Command, payload: bytes = b"", throw_error: bool = True,
                   expected_response: Optional[Tuple[Response, ...]] = None,
                   timeout: int = 5, no_response: bool = False) -> Tuple[Response, bytes]:
        if not isinstance(cmd, Command):
            raise ValueError(f"Can't MixClient.call() with non-Command action {cmd!r}")
        future = self._loop.create_future()
        if no_response:
            req_id = 0
        else:
            req_id = self.next_req_id
            self._ongoing_commands[req_id] = future
        await write(self._writer, req_id, cmd, payload)
        if no_response:
            return Response.UNKNOWN, b""
        if not self._is_listening:
            asyncio.ensure_future(self._read_one())
        resp, payload = await asyncio.wait_for(future, timeout=timeout)
        if throw_error:
            if resp == Response.ERROR:
                raise ErrorResponse(payload)
            elif ((expected_response and resp not in expected_response)
                  or not isinstance(resp, Response)):
                raise UnexpectedResponse(resp, payload, expected_response)
        return resp, payload

    async def _handle_command(self, req_id: int, cmd: Command, payload: bytes) -> None:
        try:
            return_val = await commands[cmd](self, payload)
            if isinstance(return_val, Response):
                resp = return_val
                data = b""
            else:
                resp, data = return_val
            if req_id != 0:
                await write(self._writer, req_id, resp, data)
        except Exception:
            self._log.exception("Error in command handler")
            if req_id != 0:
                await write(self._writer, req_id, Response.ERROR, b"internal error")
        try:
            del self._ongoing_commands[req_id]
        except KeyError:
            pass

    async def _read_one(self) -> bool:
        try:
            req_id, action, payload = await read(self._reader)
        except asyncio.IncompleteReadError:
            self._log.warning("Incomplete read, disconnecting...")
            return True
        except Exception:
            self._log.exception("Error reading data, disconnecting...")
            return True
        if self.is_server and action == Command.QUIT:
            self._log.info("Received QUIT, disconnecting...")
            return True
        if isinstance(action, Command):
            req_id_str = f"request #{req_id}" if req_id != 0 else "no-resp request"
            self._log.debug(f"Received {req_id_str}: {action.name}")
            task = self._loop.create_task(self._handle_command(req_id, action, payload))
            if req_id != 0:
                self._ongoing_commands[req_id] = task
        else:
            if req_id == 0:
                self._log.warning(f"Unexpected response {action.name} to req_id 0")
                return False
            self._log.debug(f"Received response to #{req_id}: {action.name}")
            future = self._ongoing_commands.pop(req_id)
            if future:
                future.set_result((action, payload))
        return False

    async def run(self) -> None:
        if self._is_listening:
            raise RuntimeError("Already listening")
        self._is_listening = True
        try:
            stop = False
            while not stop:
                stop = await self._read_one()
        except asyncio.CancelledError:
            self._log.info("Reader cancelled, disconnecting...")
        except Exception:
            self._log.exception("Fatal error in listener, disconnecting...")
        finally:
            self._is_listening = False
        try:
            await self.disconnect()
        except Exception:
            self._log.exception("Error while disconnecting")

    async def disconnect(self) -> None:
        for fut in self._ongoing_commands.values():
            fut.cancel()
        try:
            self._writer.write_eof()
            await self._writer.drain()
        except Exception as e:
            self._log.warning(f"{e} while writing EOF")
        self._writer.close()
        if sys.version_info >= (3, 7):
            await self._writer.wait_closed()

    def start(self) -> None:
        self._listen_task = self._loop.create_task(self.run())

    def stop(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
