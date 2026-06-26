from backend.services import work_type as wt


def test_category_for_known_and_groups():
    assert wt.category_for("article") == "article"
    assert wt.category_for("review") == "article"
    assert wt.category_for("book") == "book"
    assert wt.category_for("monograph") == "book"
    assert wt.category_for("book-chapter") == "book"
    assert wt.category_for("dissertation") == "thesis"
    assert wt.category_for("preprint") == "preprint"
    assert wt.category_for("dataset") == "dataset"


def test_category_for_null_and_unknown():
    assert wt.category_for(None) == "unclassified"
    assert wt.category_for("standard") == "other"
    assert wt.category_for("REPORT") == "other"
    assert wt.category_for("  Article ") == "article"


def test_category_codes_complete():
    assert wt.CATEGORY_CODES == [
        "article", "book", "thesis", "preprint", "dataset", "other", "unclassified",
    ]
