from backend.report_builder import _section_manual_note


def test_manual_report_section_escapes_analyst_input():
    html = _section_manual_note(
        "Analyst <script>alert(1)</script>",
        "Interpretation with <b>raw html</b>.\n\nSecond paragraph.",
    )

    assert "Analyst &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Interpretation with &lt;b&gt;raw html&lt;/b&gt;." in html
    assert "Second paragraph." in html
    assert "<script>" not in html
    assert "<b>raw html</b>" not in html
