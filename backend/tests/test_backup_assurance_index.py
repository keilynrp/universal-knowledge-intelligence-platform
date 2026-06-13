from backend import models


def test_backup_assurance_status_lookup_has_composite_index():
    index = next(
        (
            candidate
            for candidate in models.BackupAssuranceEvent.__table__.indexes
            if candidate.name == "ix_backup_assurance_status_lookup"
        ),
        None,
    )

    assert index is not None
    assert [column.name for column in index.columns] == [
        "environment",
        "event_type",
        "status",
        "completed_at",
        "id",
    ]
