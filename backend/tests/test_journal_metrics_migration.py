import pathlib
import re


def test_single_alembic_head():
    versions = pathlib.Path("alembic/versions")
    revisions, downs = set(), set()
    for f in versions.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        # Match revision = "id" or revision: SomeType = "id"
        if m := re.search(r'^revision\b[^=]*=\s*["\']([^"\']+)', text, re.M):
            revisions.add(m.group(1))
        # Match all quoted IDs in down_revision (handles string, tuple, and typed-annotation forms)
        for line in text.splitlines():
            if re.match(r'^\s*down_revision\b', line):
                for id_match in re.finditer(r'["\']([A-Za-z0-9]{4,})["\']', line):
                    downs.add(id_match.group(1))
    heads = revisions - downs
    assert heads == {"e6f7a8b9c0d2"}, f"expected single head e6f7a8b9c0d2, got {heads}"
