from django.db.backends.oracle.base import DatabaseWrapper as OracleDatabaseWrapper

from .operations import DatabaseOperations


class DatabaseWrapper(OracleDatabaseWrapper):
    """Oracle 19c con soporte para sus identificadores de hasta 128 bytes."""

    ops_class = DatabaseOperations
