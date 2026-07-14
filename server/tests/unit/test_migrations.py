from app.infrastructure.db.migrations import _adoption_revision


def test_empty_database_runs_migrations_from_base() -> None:
    assert _adoption_revision(set(), set()) is None


def test_unversioned_legacy_schema_is_adopted_at_initial_revision() -> None:
    assert _adoption_revision({"documents", "evidence"}, {"id", "title"}) == (
        "20260630_00"
    )


def test_unversioned_current_schema_is_adopted_before_constraint_migration() -> None:
    assert (
        _adoption_revision(
            {"documents", "evidence", "sources"},
            {"id", "source_id", "version_number", "status", "is_current"},
        )
        == "20260711_01"
    )


def test_versioned_schema_is_never_restamped() -> None:
    assert (
        _adoption_revision(
            {"alembic_version", "documents", "sources"},
            {"id", "source_id"},
        )
        is None
    )
