import datetime
import logging
import sys
from typing import *
from typing_extensions import Self

import peewee
import peewee_async

from lib.config import Config


_logger = logging.getLogger(__name__)


class Manager(peewee_async.Manager):
    """
    An extension to :class:`peewee_async.Manager` that provides some utility
    methods.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def safe_get(self, source_, *args, **kwargs) -> Optional[peewee.Model]:
        try:
            return await self.get(source_, *args, **kwargs)

        except peewee.DoesNotExist:
            return None

    async def update_fields(self, obj, **fields):
        for key, value in fields.items():
            setattr(obj, key, value)

        return await self.update(obj, only=tuple(fields.keys()))

    _manager_instance: Optional[Self] = None

    @classmethod
    def load_once(cls, force: bool = False) -> Self:
        """Ensures only one instance of :class:`Manager` exists at a time.

        :param force:
            Force reloading the database manager. Use at your own risk!
        :type force: bool

        :returns: Singleton instance.
        :rtype: Manager
        """
        if not force and cls._manager_instance is not None:
            return cls._manager_instance

        try:
            database = peewee_async.PostgresqlDatabase(**Config.db_credentials)
            cls._manager_instance = cls(database)

        except Exception as e:
            _logger.error(
                "An unexpected exception occurred while "
                "initializing the database manager:",
                exc_info=e,
            )

            sys.exit(1)

        _logger.debug("ORM Manager was loaded.")
        return cls._manager_instance


### Singleton manager instance is loaded here ###
manager: Manager = Manager.load_once()


class BaseModel(peewee.Model):
    date_created = peewee.DateTimeField(default=datetime.datetime.now)
    date_updated = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = manager.database

    @classmethod
    def create(cls, **query):
        now = datetime.datetime.now()
        query["date_created"] = now
        query["date_updated"] = now

        return super().create(**query)

    @classmethod
    def bulk_create(cls, model_list, batch_size=None):
        def lazy(models: Iterable[peewee.Model]) -> Iterable[peewee.Model]:
            now = datetime.datetime.now()
            for model in models:
                model.date_created = now
                model.date_updated = now

                yield model

        return super().bulk_create(lazy(model_list), batch_size=batch_size)

    @classmethod
    def insert(cls, __data=None, **insert):
        insert["date_updated"] = datetime.datetime.now()
        return super().insert(**insert)

    @classmethod
    def insert_many(cls, rows, fields=None):
        def lazy_tuples(rows_: Iterable[tuple]) -> Iterable[tuple]:
            now = datetime.datetime.now()
            for row in rows_:
                yield tuple([*row, now, now])

        def lazy_dicts(rows_: Iterable[dict]) -> Iterable[dict]:
            now = datetime.datetime.now()
            for row in rows_:
                row["date_created"] = now
                row["date_updated"] = now
                yield row

        if fields:
            lazy = lazy_tuples
            fields.append("date_created")
            fields.append("date_updated")

        else:
            lazy = lazy_dicts

        return super().insert_many(lazy(rows), fields)

    @classmethod
    def insert_from(cls, query, fields):
        field_names: list[str] = [
            field.column_name if isinstance(field, peewee.Field) else field
            for field in fields
        ]

        def lazy(query_: peewee.Select):
            for row in query_:
                values = []
                for field_name in field_names:
                    values.append(getattr(row, field_name))
                yield tuple(values)

        return cls.insert_many(lazy(query), fields=field_names)

    @classmethod
    def replace(cls, __data=None, **insert):
        now = datetime.datetime.now()
        insert["date_created"] = now
        insert["date_updated"] = now
        return super().replace(data, **insert)

    @classmethod
    def replace_many(cls, rows, fields=None):
        return cls.insert_many(rows=row, fields=fields).on_conflict("REPLACE")

    @classmethod
    def update(cls, __data=None, **update):
        if "date_updated" not in update:
            update["date_updated"] = datetime.datetime.now()
        return super().update(__data, **update)

    @classmethod
    def bulk_update(cls, model_list, fields, batch_size=None):
        def lazy(models: Iterable[peewee.Model]) -> Iterable[peewee.Model]:
            now = datetime.datetime.now()
            for model in models:
                model.date_updated = now

                yield model

        fields = list(fields)
        fields.append("date_updated")

        return super().bulk_update(lazy(model_list), fields, batch_size=batch_size)
