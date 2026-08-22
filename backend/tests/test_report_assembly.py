"""Document assembly: exhibit ordinals and the executive summary.

These test the *assembly*, not the sections. Each collector is covered
elsewhere; what is pinned here is what only `build()` can decide — where a
section sits in one document, and which findings lead.
"""
import re

import pytest

from backend.reporting.section_data import Materiality, SectionData

pytestmark = pytest.mark.reporting


def _summary(html: str) -> str:
    match = re.search(r"<h2>Executive Summary</h2>.*?</section>", html, re.S)
    return match.group(0) if match else ""


def _entries(summary_html: str) -> list[tuple[bool, str]]:
    """(is_muted, text) per summary line, in rendered order."""
    out = []
    for item in re.findall(r"<li[^>]*>.*?</li>", summary_html, re.S):
        opening = item.split(">", 1)[0]
        text = re.sub(r"<[^>]+>", "", item).replace("&nbsp;", " ")
        out.append(("muted" in opening, " ".join(text.split())))
    return out


def _generate(client, auth_headers, sections: list[str]) -> str:
    resp = client.post(
        "/reports/generate",
        json={"domain_id": "default", "sections": sections, "title": "Assembly"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text[:300]
    return resp.text


# ── Exhibit ordinals ──────────────────────────────────────────────────────────


def test_exhibits_are_numbered_in_document_order(client, auth_headers):
    html = _generate(client, auth_headers, ["entity_stats", "harmonization_log"])
    numbers = [int(n) for n in re.findall(r"Exhibit (\d+)", _summary(html))]
    assert sorted(numbers) == list(range(1, len(numbers) + 1)), (
        f"ordinals are not a gapless 1..n sequence: {numbers}"
    )


def test_ordinals_shift_with_selection_but_keys_do_not(client, auth_headers):
    """An ordinal is a within-document reference; `key` is the stable identifier.

    The same section numbered differently in two reports is expected, and is why
    citation guidance has to point at the key rather than "Exhibit 4".
    """
    alone = _generate(client, auth_headers, ["harmonization_log"])
    preceded = _generate(client, auth_headers, ["entity_stats", "harmonization_log"])

    def ordinal_of(html: str, needle: str) -> int:
        for _, text in _entries(_summary(html)):
            if needle in text:
                return int(re.search(r"Exhibit (\d+)", text).group(1))
        raise AssertionError(f"{needle!r} not in summary")

    assert ordinal_of(alone, "harmonization") == 1
    assert ordinal_of(preceded, "harmonization") == 2

    # The key is unchanged in both, which is the point of the contrast.
    assert "harmonization_log" in alone or "Harmonization" in alone
    assert "harmonization_log" in preceded or "Harmonization" in preceded


def test_the_ordinal_the_summary_cites_is_findable_on_the_section(client, auth_headers):
    """An exhibit number a reader cannot locate in the body is a dead reference."""
    html = _generate(client, auth_headers, ["entity_stats", "harmonization_log"])
    summary = _summary(html)
    body = html.replace(summary, "")

    for ordinal in (1, 2):
        assert f"Exhibit {ordinal}" in summary
        assert f"Exhibit {ordinal}" in body, (
            f"the summary cites Exhibit {ordinal} but no section announces it"
        )


# ── Method disclosure ─────────────────────────────────────────────────────────


def test_every_rendered_section_discloses_its_method(client, auth_headers):
    """Mandatory, not conditional: one disclosure per rendered section."""
    requested = ["entity_stats", "harmonization_log", "topic_clusters"]
    html = _generate(client, auth_headers, requested)
    body = html.replace(_summary(html), "")

    # +1 for the stakeholder lens, which is rendered ahead of the exhibits and
    # carries the same contract.
    assert body.count('class="method"') == len(requested) + 1


def test_presentation_elements_are_styled():
    """A class no stylesheet rule matches renders as unstyled text.

    Task 3.5 found exactly that in production: a section styled itself with
    `class="card"` and `class="muted"`, neither of which the stylesheet defined.
    Emitting a class is only half of adding a presentation element.
    """
    from backend.report_builder import _CSS

    for cls in ("exhibit-label", "method", "summary-list", "muted"):
        assert f".{cls}" in _CSS, f"{cls} is emitted but never styled"


# ── Executive summary ─────────────────────────────────────────────────────────


def test_summary_lists_every_rendered_section(client, auth_headers):
    """Ordered, not filtered: a section that computed and found nothing still
    appears, so a reader can tell it ran."""
    requested = ["entity_stats", "harmonization_log", "topic_clusters"]
    entries = _entries(_summary(_generate(client, auth_headers, requested)))
    assert len(entries) == len(requested)


def test_summary_leads_with_material_findings(client, auth_headers):
    html = _generate(
        client, auth_headers,
        ["entity_stats", "harmonization_log", "institutional_benchmark"],
    )
    entries = _entries(_summary(html))
    muted_flags = [muted for muted, _ in entries]
    # Once a muted entry appears, everything after it is muted too — that is
    # what "ordered by materiality" means for the reader.
    assert muted_flags == sorted(muted_flags), (
        f"material and non-material entries are interleaved: {entries}"
    )


def test_empty_sections_are_de_emphasised_not_dropped(client, auth_headers):
    entries = _entries(_summary(_generate(client, auth_headers, ["harmonization_log"])))
    assert len(entries) == 1
    muted, text = entries[0]
    assert muted, "a section with nothing to report should be de-emphasised"
    assert "No harmonization operations" in text


def test_summary_never_shows_a_raw_catalog_key(client, auth_headers):
    """The executive summary reads `takeaway` off the collected payload, and it
    is not a renderer — so it does not get the localization every renderer
    performs on what it is handed.

    That gap shipped: five takeaways were migrated to catalog keys in earlier
    batches, and an empty one of those sections printed `report.takeaway.…`
    verbatim in a real report. Only one test covered the path, and it happened
    to assert on the single takeaway still holding literal English.

    So assert the property, not one section's wording: no summary entry may
    contain a key from any surface. A section migrating its takeaway tomorrow is
    covered without anyone remembering to extend this.
    """
    html = _generate(
        client, auth_headers,
        ["entity_stats", "harmonization_log", "topic_clusters", "agentic_trace"],
    )
    for _muted, text in _entries(_summary(html)):
        assert not any(
            token.startswith(("report.", "email.", "validation.", "chat.", "ops."))
            for token in text.split()
        ), f"the summary shows an unresolved catalog key: {text!r}"


def test_summary_escapes_takeaway_text(client, auth_headers):
    """Takeaways are data. A section name or label containing markup must not
    reach the document as markup."""
    html = _generate(client, auth_headers, ["institutional_benchmark"])
    summary = _summary(html)
    assert "<script>" not in summary


# ── The ordinal contract itself ───────────────────────────────────────────────


def test_section_data_carries_no_ordinal_until_assembly():
    """A collector cannot know it is Exhibit 4 — that depends on the request."""
    section = SectionData(key="k", title="T", takeaway="a finding", method="a source")
    assert section.exhibit is None
    assert section.materiality is Materiality.ROUTINE
