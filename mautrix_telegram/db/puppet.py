# -*- coding: future_fstrings -*-
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
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.engine.result import RowProxy
from sqlalchemy.sql import expression, and_
from typing import Optional, Iterable

from ..types import MatrixUserID, TelegramID
from .base import Base


class Puppet(Base):
    __tablename__ = "puppet"

    id = Column(Integer, primary_key=True)  # type: TelegramID
    custom_mxid = Column(String, nullable=True)  # type: Optional[MatrixUserID]
    access_token = Column(String, nullable=True)
    displayname = Column(String, nullable=True)
    displayname_source = Column(Integer, nullable=True)  # type: Optional[TelegramID]
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    photo_id = Column(String, nullable=True)
    is_bot = Column(Boolean, nullable=True)
    matrix_registered = Column(Boolean, nullable=False, server_default=expression.false())
    disable_updates = Column(Boolean, nullable=False, server_default=expression.false())

    @classmethod
    def scan(cls, row) -> Optional['Puppet']:
        (id, custom_mxid, access_token, displayname, displayname_source, username, first_name,
         last_name, photo_id, is_bot, matrix_registered, disable_updates) = row
        return cls(id=id, custom_mxid=custom_mxid, access_token=access_token,
                   displayname=displayname, displayname_source=displayname_source,
                   username=username, first_name=first_name, last_name=last_name,
                   photo_id=photo_id, is_bot=is_bot, matrix_registered=matrix_registered,
                   disable_updates=disable_updates)

    @classmethod
    def _one_or_none(cls, rows: RowProxy) -> Optional['Puppet']:
        try:
            return cls.scan(next(rows))
        except StopIteration:
            return None

    @classmethod
    def all_with_custom_mxid(cls) -> Iterable['Puppet']:
        rows = cls.db.execute(cls.t.select().where(cls.c.custom_mxid != None))
        for row in rows:
            yield cls.scan(row)

    @classmethod
    def get_by_tgid(cls, tgid: TelegramID) -> Optional['Puppet']:
        return cls._select_one_or_none(cls.c.id == tgid)

    @classmethod
    def get_by_custom_mxid(cls, mxid: MatrixUserID) -> Optional['Puppet']:
        return cls._select_one_or_none(cls.c.custom_mxid == mxid)

    @classmethod
    def get_by_username(cls, username: str) -> Optional['Puppet']:
        return cls._select_one_or_none(cls.c.username == username)

    @classmethod
    def get_by_displayname(cls, displayname: str) -> Optional['Puppet']:
        return cls._select_one_or_none(cls.c.displayname == displayname)

    @property
    def _edit_identity(self):
        return self.c.id == self.id

    def insert(self) -> None:
        with self.db.begin() as conn:
            conn.execute(self.t.insert().values(
                id=self.id, custom_mxid=self.custom_mxid, access_token=self.access_token,
                displayname=self.displayname, displayname_source=self.displayname_source,
                username=self.username, first_name=self.first_name, last_name=self.last_name,
                photo_id=self.photo_id, is_bot=self.is_bot,
                matrix_registered=self.matrix_registered, disable_updates=self.disable_updates))


class PuppetPortal(Base):
    __tablename__ = "puppet_portal"

    puppet_id = Column(Integer, ForeignKey("puppet.id"), primary_key=True)
    portal_id = Column(Integer, ForeignKey("portal.id"), primary_key=True)  # type: TelegramID
    displayname = Column(String(255), nullable=True)

    @property
    def _edit_identity(self):
        return and_(self.c.puppet_id == self.puppet_id, self.c.portal_id == self.portal_id)

    def insert(self) -> None:
        with self.db.begin() as conn:
            conn.execute(self.t.insert().values(puppet_id=self.puppet_id, portal_id=self.portal_id,
                                                displayname=self.displayname))

    @classmethod
    def scan(cls, row) -> Optional['PuppetPortal']:
        (puppet_id, portal_id, displayname) = row
        return cls(puppet_id=puppet_id, portal_id=portal_id, displayname=displayname)

    @classmethod
    def _one_or_none(cls, rows: RowProxy) -> Optional['PuppetPortal']:
        try:
            return cls.scan(next(rows))
        except StopIteration:
            return None

    @classmethod
    def all_for_puppet(cls, puppet_id: int) -> Iterable['PuppetPortal']:
        rows = cls.db.execute(cls.t.select().where(cls.c.puppet_id == puppet_id))
        for row in rows:
            yield cls.scan(row)

    @classmethod
    def get(cls, puppet_id: int, portal_id: int) -> Optional['PuppetPortal']:
        return cls._one_or_none(cls.db.execute(cls.t.select().where(
            and_(cls.c.puppet_id == puppet_id, cls.c.portal_id == portal_id))))
