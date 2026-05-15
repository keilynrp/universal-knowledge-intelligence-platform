from pathlib import Path
import re


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def test_migrations_do_not_destructively_modify_user_avatars():
    destructive_patterns = [
        re.compile(r"drop_column\(\s*['\"]avatar_url['\"]"),
        re.compile(r"drop_column\(\s*['\"]users['\"]\s*,\s*['\"]avatar_url['\"]"),
        re.compile(r"UPDATE\s+users\s+SET\s+avatar_url\s*=\s*NULL", re.IGNORECASE),
        re.compile(r"UPDATE\s+users\s+SET\s+avatar_url\s*=\s*''", re.IGNORECASE),
        re.compile(r"ALTER\s+TABLE\s+users\s+DROP\s+COLUMN\s+avatar_url", re.IGNORECASE),
    ]

    offenders = []
    for migration in MIGRATIONS_DIR.glob("*.py"):
        content = migration.read_text(encoding="utf-8")
        for pattern in destructive_patterns:
            if pattern.search(content):
                offenders.append(migration.name)
                break

    assert offenders == []
