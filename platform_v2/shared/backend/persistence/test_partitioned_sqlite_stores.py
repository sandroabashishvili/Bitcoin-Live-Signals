"""Regression tests for the three-database persistence boundaries."""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.persistence.sqlite_content_store import (
    content_database_status,
    read_news_batch,
    replace_news_batch,
)
from platform_v2.shared.backend.persistence.sqlite_market_data_store import (
    market_database_status,
    market_series_parity,
    read_market_series,
    replace_market_series,
    replace_market_series_safely,
)
from platform_v2.shared.backend.persistence.sqlite_runtime_state import (
    read_runtime_state,
    write_runtime_state,
)


def test_market_database_preserves_venue_and_market_boundaries(tmp_path: Path) -> None:
    db_path = tmp_path / "market.sqlite3"
    spot_rows = [{"timestamp": 1000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 3}]
    futures_rows = [{"timestamp": 1000, "open": 20, "high": 22, "low": 19, "close": 21, "volume": 7}]
    for market_type, rows in (("spot", spot_rows), ("futures", futures_rows)):
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type=market_type,
            dataset="candles",
            symbol="BTCUSDT",
            timeframe="15m",
            rows=rows,
            db_path=db_path,
        )

    assert read_market_series(
        venue="binance",
        asset_class="crypto",
        market_type="spot",
        dataset="candles",
        symbol="BTCUSDT",
        timeframe="15m",
        db_path=db_path,
    ) == spot_rows
    assert market_series_parity(
        rows=futures_rows,
        venue="binance",
        asset_class="crypto",
        market_type="futures",
        dataset="candles",
        symbol="BTCUSDT",
        timeframe="15m",
        db_path=db_path,
    )
    assert market_database_status(db_path)["series"] == 2


def test_first_market_read_after_clean_reset_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh" / "market.sqlite3"

    assert read_market_series(
        venue="binance",
        asset_class="crypto",
        market_type="futures",
        dataset="candles",
        symbol="BTCUSDT",
        timeframe="1m",
        db_path=db_path,
    ) == []
    assert db_path.exists()
    assert market_database_status(db_path)["series"] == 0


def test_temporary_market_writer_path_does_not_touch_live_database(tmp_path: Path) -> None:
    assert not replace_market_series_safely(
        venue="binance",
        asset_class="crypto",
        market_type="spot",
        dataset="indicators",
        symbol="BTCUSDT",
        timeframe="15m",
        rows=[{"timestamp": 1, "rsi": 50}],
        source_path=tmp_path / "15m.json",
    )


def test_content_database_round_trips_news_batch(tmp_path: Path) -> None:
    db_path = tmp_path / "content.sqlite3"
    items = [{"title": "Headline", "link": "https://example.com/a", "source": "Example", "summary": "Summary", "pub_ts": 123}]
    replace_news_batch(
        day_iso="2026-08-01",
        generated_at_utc="2026-08-01 10:00:00 UTC",
        items=items,
        db_path=db_path,
    )
    assert read_news_batch("2026-08-01", db_path=db_path) == items
    assert content_database_status(db_path)["articles"] == 1


def test_trading_database_keeps_mutable_engine_state(tmp_path: Path) -> None:
    db_path = tmp_path / "trading.sqlite3"
    state = {"next_position_id": 7, "open_positions": []}
    write_runtime_state(system="futures", state_key="simulation_engine", payload=state, db_path=db_path)
    assert read_runtime_state(
        system="futures",
        state_key="simulation_engine",
        db_path=db_path,
    ) == state
