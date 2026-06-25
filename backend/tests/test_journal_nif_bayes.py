import importlib.util
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_head_is_nif_bayes():
    cfg = Config("alembic.ini")
    heads = set(ScriptDirectory.from_config(cfg).get_heads())
    assert heads == {"d6e7f8a9b0c1"}, f"expected single head d6e7f8a9b0c1, got {heads}"


def test_journalmetric_has_bayes_columns():
    from backend.models import JournalMetric
    cols = set(JournalMetric.__table__.columns.keys())
    assert {"works_2yr", "nif_bayes", "nif_ci_low",
            "nif_ci_high", "nif_bayes_updated_at"} <= cols
