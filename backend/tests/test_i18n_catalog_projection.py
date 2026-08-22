"""The committed JSON projection of the frontend message catalog.

`frontend/app/i18n/translations.ts` is TypeScript, so the backend cannot import
it. A generator emits a JSON projection the backend can load, and CI fails when
the committed projection disagrees with its source — a projection that drifts
from the catalog it mirrors is the exact defect this capability exists to
prevent.

These tests assert properties of the **committed artefact**, which needs no
Node and no regeneration, so they hold in every job that runs the backend
suite. Whether regeneration reproduces the file byte for byte is proved by the
generator's own `--check` mode in CI, not here: a test that silently skips when
Node is absent would be a gate that cannot fail.
"""

import json

import pytest

from backend.i18n import CATALOG_DIR, LANGUAGES

pytestmark = pytest.mark.reporting


def _load(language: str) -> dict:
    path = CATALOG_DIR / f"catalog.{language}.json"
    assert path.exists(), f"the {language} projection is missing — run the generator"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", LANGUAGES)
class TestProjectionShape:
    def test_projection_is_a_flat_string_map(self, language):
        catalog = _load(language)

        assert isinstance(catalog, dict) and catalog, "the projection is empty"
        bad = {k: v for k, v in catalog.items() if not isinstance(v, str)}
        assert not bad, (
            f"the catalog is a flat key→string map; {language} has non-string "
            f"values at {sorted(bad)[:5]}"
        )

    def test_keys_are_sorted(self, language):
        """Sorted output is what makes regeneration deterministic.

        Without a defined order the file re-emits in whatever order the parser
        walked the source, and every unrelated PR carries a phantom diff.
        """
        keys = list(_load(language))

        assert keys == sorted(keys), (
            f"the {language} projection is not key-sorted, so regenerating it "
            f"produces diff noise and the drift gate cannot be trusted"
        )

    def test_no_key_is_blank(self, language):
        catalog = _load(language)

        assert all(k.strip() for k in catalog), "the projection contains a blank key"


class TestParity:
    """A second reading of the parity contract, from the backend's side.

    `scripts/check-i18n-parity.mjs` is the gate; this is not a substitute for
    it, because it cannot see `translations.ts` (the source) and the gate can.
    It exists because the projection is what the backend actually loads, and a
    one-sided key there is a report rendering a bare key to a reader. Catching
    that in the suite everyone runs is worth the overlap.
    """

    def test_english_and_spanish_hold_the_same_keys(self):
        english, spanish = set(_load("en")), set(_load("es"))

        missing_es = sorted(english - spanish)
        missing_en = sorted(spanish - english)
        assert not missing_es and not missing_en, (
            f"{len(missing_es)} key(s) absent from Spanish (e.g. {missing_es[:3]}), "
            f"{len(missing_en)} absent from English (e.g. {missing_en[:3]})"
        )

    def test_parity_is_checked_against_more_than_a_count(self):
        """Equal totals are not parity — two catalogs can differ key for key.

        Asserting `len(en) == len(es)` would pass while every key differed, so
        the test above compares sets. This one pins that intent so a future
        simplification to a length check is a deliberate act, not a slip.
        """
        english, spanish = set(_load("en")), set(_load("es"))

        assert english == spanish


class TestProjectionMatchesSource:
    def test_every_key_in_the_source_survives_the_projection(self):
        """The projection is a mirror, not a subset.

        Counted off the source directly rather than trusting the generator that
        wrote the file: a generator that drops keys and a test that reads only
        the generator's output would agree with each other and both be wrong.
        """
        source = (CATALOG_DIR.parents[1] / "frontend/app/i18n/translations.ts").read_text(
            encoding="utf-8"
        )
        # `    'some.key': '...'` — the catalog's only key form.
        import re

        blocks = re.split(r"^ {4}(en|es): \{$", source, flags=re.MULTILINE)
        assert len(blocks) == 5, "translations.ts no longer has exactly an en and an es block"

        for language, body in ((blocks[1], blocks[2]), (blocks[3], blocks[4])):
            source_keys = set(re.findall(r"^\s+'([^']+)':", body, flags=re.MULTILINE))
            projected = set(_load(language))
            missing = source_keys - projected
            assert not missing, (
                f"{len(missing)} {language} keys are in translations.ts but not in the "
                f"projection, e.g. {sorted(missing)[:5]}"
            )
