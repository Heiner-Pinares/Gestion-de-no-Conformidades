from django.db.backends.oracle.operations import (
    DatabaseOperations as OracleDatabaseOperations,
)


class DatabaseOperations(OracleDatabaseOperations):
    def max_name_length(self):
        # Desde Oracle 12.2 el límite es 128 bytes; el portal exige Oracle 19c.
        return 128
