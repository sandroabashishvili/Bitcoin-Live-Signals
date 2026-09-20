"""Regression tests for full runtime-reset semantics."""

from pathlib import Path

from platform_v2.tools.runtime_reset_system.cli import _run_full_reset


def test_full_reset_archives_complete_runtime_roots_without_recreating_them(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    database = runtime / "database"
    spot = runtime / "spot"
    futures = runtime / "futures"
    hedge = runtime / "hedge"
    archive = tmp_path / "archives" / "reset"
    for root in (database, spot, futures, hedge):
        root.mkdir(parents=True)
        (root / "sentinel.txt").write_text(root.name, encoding="utf-8")
    (futures / "state").mkdir()
    (futures / "state" / "engine.json").write_text("{}", encoding="utf-8")

    archived = _run_full_reset(
        database_root=database,
        spot_root=spot,
        futures_root=futures,
        hedge_root=hedge,
        archive_dir=archive,
        dry_run=False,
    )

    assert archived == ["database", "spot", "futures", "hedge"]
    assert not database.exists()
    assert not spot.exists()
    assert not futures.exists()
    assert not hedge.exists()
    assert (archive / "futures" / "state" / "engine.json").exists()
