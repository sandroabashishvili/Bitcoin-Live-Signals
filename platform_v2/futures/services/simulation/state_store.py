"""Engine state store and migration helpers for Futures simulation."""

from __future__ import annotations

import json
from typing import Any

from platform_v2.futures.storage import engine_state_path
from platform_v2.futures.services.account import FuturesFeeService
from platform_v2.shared.backend.persistence import read_runtime_state, write_runtime_state

from .common import coerce_int, utc_now_ms


class FuturesSimulationStateStore:
    _STATE_KEY = "simulation_engine"

    def load(self) -> dict[str, Any]:
        path = engine_state_path()
        payload = read_runtime_state(system="futures", state_key=self._STATE_KEY)
        if payload is None:
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    payload = {}
            else:
                payload = self._default_state()
        if not isinstance(payload, dict):
            payload = {}
        self._migrate(payload)
        self.save(payload)
        return payload

    def save(self, state: dict[str, Any]) -> None:
        write_runtime_state(system="futures", state_key=self._STATE_KEY, payload=state)

    @staticmethod
    def open_positions(state: dict[str, Any]) -> list[dict[str, Any]]:
        payload = state.get("open_positions")
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        legacy = state.get("open_position")
        if isinstance(legacy, dict):
            return [legacy]
        return []

    @staticmethod
    def set_open_positions(state: dict[str, Any], positions: list[dict[str, Any]]) -> None:
        state["open_positions"] = positions
        state["open_position"] = positions[0] if positions else None

    def _default_state(self) -> dict[str, Any]:
        return {
            "started_at_ms": utc_now_ms(),
            "next_position_id": 1,
            "open_positions": [],
            "last_entry_price": None,
            "last_entry_ts_ms": None,
            "manual_entry_block": False,
            "stats": {
                "total_positions": 0,
                "closed_positions": 0,
                "tp_hits": 0,
                "sl_hits": 0,
                "profit_lock_hits": 0,
                "force_close_events": 0,
                "force_closes_by_reason": {},
                "total_gross_pnl": 0.0,
                "total_fees_paid": 0.0,
                "total_net_pnl": 0.0,
            },
            "last_position_event": "NO_EVENT",
        }

    def _migrate(self, payload: dict[str, Any]) -> None:
        payload.setdefault("started_at_ms", utc_now_ms())
        payload.setdefault("next_position_id", 1)
        payload.setdefault("last_position_event", "NO_EVENT")
        payload.setdefault("last_entry_price", None)
        payload.setdefault("last_entry_ts_ms", None)
        payload.setdefault("manual_entry_block", False)

        open_positions = self.open_positions(payload)
        self.set_open_positions(payload, open_positions)
        for open_position in open_positions:
            notional = float(open_position.get("notional_usdt", 0.0) or 0.0)
            if "entry_fee_paid" not in open_position:
                open_position["entry_fee_paid"] = round(
                    FuturesFeeService.entry_fee_for_notional(notional),
                    2,
                )
            open_position.setdefault("entry_fee_role", FuturesFeeService.TAKER)
            open_position.setdefault(
                "entry_fee_rate",
                FuturesFeeService.fee_rate_for_role(str(open_position.get("entry_fee_role") or FuturesFeeService.TAKER)),
            )
        if payload.get("last_entry_price") is None and open_positions:
            payload["last_entry_price"] = open_positions[-1].get("entry_price")
        if payload.get("last_entry_ts_ms") is None and open_positions:
            payload["last_entry_ts_ms"] = open_positions[-1].get("opened_at_ms")

        stats = payload.setdefault("stats", {})
        if not isinstance(stats, dict):
            stats = {}
            payload["stats"] = stats
        stats.setdefault("total_positions", 0)
        stats.setdefault("closed_positions", 0)
        stats.setdefault("tp_hits", 0)
        stats.setdefault("sl_hits", 0)
        stats.setdefault("profit_lock_hits", 0)
        stats.setdefault("force_close_events", 0)
        stats.setdefault("force_closes_by_reason", {})
        stats.setdefault("total_gross_pnl", 0.0)
        stats.setdefault("total_fees_paid", 0.0)
        stats.setdefault("total_net_pnl", 0.0)
        payload["next_position_id"] = max(1, coerce_int(payload.get("next_position_id")))
