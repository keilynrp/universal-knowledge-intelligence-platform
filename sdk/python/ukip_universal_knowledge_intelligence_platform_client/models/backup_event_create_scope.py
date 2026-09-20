from enum import Enum


class BackupEventCreateScope(str, Enum):
    DATABASE = "database"
    VOLUME = "volume"

    def __str__(self) -> str:
        return str(self.value)
