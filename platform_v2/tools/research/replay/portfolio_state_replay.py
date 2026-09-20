"""Replay candidate profiles with the live portfolio permission/state model.

Unlike ``candidate_signal_outcome_replay``, this tool does not treat every
signal as an independent trade.  It processes entries chronologically, closes
positions on 5m candles, reserves capital while positions are open, and applies
the current Spot/Futures permission checks before accepting a new position.

This remains a research replay.  It intentionally does not mutate runtime data
or live strategy settings.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures.domain.models.signal import SignalSide as FuturesSignalSide
from platform_v2.futures.domain.flip_confirmation import FlipConfirmationTracker
from platform_v2.futures.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as FuturesIndicatorRepository,
)
from platform_v2.futures.services.analytics.trade_audit.entry_location_classifier import (
    EntryLocationClassifier as FuturesEntryLocationClassifier,
)
from platform_v2.futures.services.permission.futures_permission_decision_service import (
    FuturesPermissionDecisionService,
)
from platform_v2.futures.services.trading.futures_sl_tp_service import (
    StopLossTakeProfitService as FuturesSlTpService,
)
from platform_v2.spot.config import settings as spot_settings
from platform_v2.spot.domain.models.signal import SignalSide as SpotSignalSide
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as SpotIndicatorRepository,
)
from platform_v2.spot.services.trading.sl_tp_service import (
    StopLossTakeProfitService as SpotSlTpService,
)
from platform_v2.spot.services.trading.setup_confidence import normalized_setup_confidence
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots
from platform_v2.tools.research.replay.candidate_profiles import PROFILES, CandidateProfile
from platform_v2.tools.research.replay.candidate_signal_outcome_replay import (
    _candle_rows,
    _outcome,
)
from platform_v2.tools.research.replay.historical_component_replay import (
    _float,
    _indicator_index,
    _reconstruct_futures,
    _reconstruct_spot,
)
from platform_v2.tools.research.replay.indicator_candidate_adjustments import adjusted_components
from platform_v2.tools.research.replay.candidate_entry_policies import (
    evaluate_entry_policy,
    flip_confirmation_sides,
)
from platform_v2.tools.research.replay.candidate_exit_policies import (
    adjust_exit_levels,
)
from platform_v2.tools.research.replay.candidate_position_management import managed_outcome
from platform_v2.tools.research.replay.portfolio_replay_permissions import (
    gate_count,
    short_market_plan_ok,
    spot_permission_reason,
    timing_context,
)
from platform_v2.tools.research.replay.portfolio_replay_context import build_market_context_7d
from platform_v2.tools.research.replay.portfolio_replay_features import (
    entry_features,
    exit_geometry_features,
)
from platform_v2.tools.research.replay.portfolio_outcome_audit import build_outcome_audit
from platform_v2.tools.research.replay.portfolio_replay_report import write_report
from platform_v2.tools.research.replay.portfolio_replay_state import (
    OpenPosition,
    actual_closed_performance,
    actual_open_timestamps,
    close_due_positions,
    load_family_rows,
    portfolio_stats,
    validation,
)
from platform_v2.tools.research.replay.spot_force_close_replay import (
    apply_minus_rule_force_closes,
)


def _spot_profile_replay(
    *,
    profile: CandidateProfile,
    rows: list[dict[str, Any]],
    snapshots: Any,
    candles: list[dict[str, Any]],
    actual_timestamps: list[int],
    split_timestamp_ms: int,
    period_origin_timestamp_ms: int,
) -> dict[str, Any]:
    candle_timestamps = [int(row["timestamp_ms"]) for row in candles]
    sl_tp = SpotSlTpService()
    opened: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    open_positions: list[OpenPosition] = []
    blockers: Counter[str] = Counter()
    realized_net_pnl = 0.0
    actionable = 0
    actual_timestamp_set = {int(value) for value in actual_timestamps}
    actual_timestamp_trace: list[dict[str, Any]] = []

    for row in rows:
        timestamp_ms = int(row["timestamp_ms"])
        open_positions, newly_closed = close_due_positions(
            open_positions=open_positions,
            timestamp_ms=timestamp_ms,
        )
        closed.extend(newly_closed)
        realized_net_pnl += sum(_float(item.get("net_pnl")) for item in newly_closed)
        open_positions, force_closed = apply_minus_rule_force_closes(
            open_positions=open_positions,
            timestamp_ms=timestamp_ms,
            candles=candles,
            candle_timestamps=candle_timestamps,
            weak_open_position_pct=float(spot_settings.WEAK_OPEN_POSITION_PCT),
            exit_fee_rate=float(spot_settings.EXIT_FEE_PCT),
        )
        closed.extend(force_closed)
        realized_net_pnl += sum(_float(item.get("net_pnl")) for item in force_closed)
        snapshot = snapshots.at(timestamp_ms)
        if snapshot is None:
            blockers["missing_snapshot"] += 1
            if timestamp_ms in actual_timestamp_set:
                actual_timestamp_trace.append(
                    {"timestamp_ms": timestamp_ms, "status": "missing_snapshot"}
                )
            continue
        components = adjusted_components(
            profile=profile,
            components=row["components"],
            snapshot=snapshot,
        )
        score = profile.score(components)
        if score < profile.threshold:
            if timestamp_ms in actual_timestamp_set:
                actual_timestamp_trace.append(
                    {
                        "timestamp_ms": timestamp_ms,
                        "status": "below_threshold",
                        "score": score,
                        "threshold": profile.threshold,
                        "component_scores": components,
                    }
                )
            continue
        actionable += 1
        price = float(snapshot.price)
        setup = sl_tp.build_theoretical_setup(
            side=SpotSignalSide.BUY,
            entry_price=price,
            snapshot=snapshot,
            confidence=normalized_setup_confidence(score),
        )
        if setup is None:
            blockers["missing_setup"] += 1
            if timestamp_ms in actual_timestamp_set:
                actual_timestamp_trace.append(
                    {
                        "timestamp_ms": timestamp_ms,
                        "status": "missing_setup",
                        "score": score,
                        "component_scores": components,
                    }
                )
            continue
        features = {
            **entry_features(snapshot=snapshot, side="BUY"),
            **exit_geometry_features(
                entry=price,
                stop_loss=float(setup.stop_loss),
                take_profit=float(setup.take_profit),
                atr=snapshot.atr,
            ),
        }
        reason = spot_permission_reason(
            price=price,
            snapshot=snapshot,
            open_positions=open_positions,
            realized_net_pnl=realized_net_pnl,
            timestamp_ms=timestamp_ms,
        )
        if reason != "allowed":
            blockers[reason] += 1
            if timestamp_ms in actual_timestamp_set:
                actual_timestamp_trace.append(
                    {
                        "timestamp_ms": timestamp_ms,
                        "status": "permission_denied",
                        "reason": reason,
                        "score": score,
                        "component_scores": components,
                    }
                )
            continue
        outcome = _outcome(
            candles=candles,
            candle_timestamps=candle_timestamps,
            entry_timestamp_ms=timestamp_ms,
            side="BUY",
            entry=price,
            stop_loss=float(setup.stop_loss),
            take_profit=float(setup.take_profit),
            notional=float(spot_settings.DEFAULT_POSITION_SIZE),
            entry_fee_rate=float(spot_settings.ENTRY_FEE_PCT),
            exit_fee_rate=float(spot_settings.EXIT_FEE_PCT),
        )
        if outcome is None:
            blockers["missing_outcome"] += 1
            if timestamp_ms in actual_timestamp_set:
                actual_timestamp_trace.append(
                    {
                        "timestamp_ms": timestamp_ms,
                        "status": "missing_outcome",
                        "score": score,
                        "component_scores": components,
                    }
                )
            continue
        outcome = {
            **outcome,
            "score": score,
            "component_scores": components,
            "features": features,
            "permission": "allowed",
        }
        opened.append(outcome)
        if timestamp_ms in actual_timestamp_set:
            actual_timestamp_trace.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "status": "opened",
                    "score": score,
                    "component_scores": components,
                }
            )
        open_positions.append(
            OpenPosition(
                side="BUY",
                entry_timestamp_ms=timestamp_ms,
                entry=price,
                margin=float(spot_settings.DEFAULT_POSITION_SIZE),
                entry_fee=float(spot_settings.DEFAULT_POSITION_SIZE * spot_settings.ENTRY_FEE_PCT),
                outcome=outcome,
            )
        )

    return {
        "profile": profile.__dict__,
        "evaluated_signal_rows": len(rows),
        "actionable_signals": actionable,
        "permission_blockers": dict(blockers.most_common()),
        "force_close_events": sum(
            str(row.get("resolution") or "") == "FORCE_CLOSE" for row in closed
        ),
        "portfolio": portfolio_stats(
            opened=opened,
            closed=closed,
            open_positions=open_positions,
            split_timestamp_ms=split_timestamp_ms,
            period_origin_timestamp_ms=period_origin_timestamp_ms,
        ),
        "baseline_validation": validation(
            (row["entry_timestamp_ms"] for row in opened),
            actual_timestamps,
        ),
        "opened_outcomes": opened,
        "closed_outcomes": closed,
        "force_close_outcomes": [
            row
            for row in closed
            if str(row.get("resolution") or "") == "FORCE_CLOSE"
        ],
        "actual_timestamp_trace": actual_timestamp_trace,
    }


def _futures_profile_replay(
    *,
    long_profile: CandidateProfile,
    short_profile: CandidateProfile,
    by_timestamp: dict[int, dict[str, dict[str, Any]]],
    snapshots: Any,
    candles: list[dict[str, Any]],
    plans: dict[int, dict[str, Any]],
    actual_timestamps: dict[str, list[int]],
    split_timestamp_ms: int,
    period_origin_timestamp_ms: int,
) -> dict[str, Any]:
    candle_timestamps = [int(row["timestamp_ms"]) for row in candles]
    # Keep the frozen baseline setup unchanged; candidate exit policies are
    # applied explicitly below so historical control and promoted live policy
    # do not collapse into the same replay arm.
    sl_tp = FuturesSlTpService(short_stop_cap_enabled=False)
    permission_service = FuturesPermissionDecisionService()
    opened: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    open_positions: list[OpenPosition] = []
    blockers: Counter[str] = Counter()
    selected_counts: Counter[str] = Counter()
    realized_net_pnl = 0.0
    prior_selected_sides: list[str] = []
    confirmation_sides = flip_confirmation_sides(profiles=(long_profile, short_profile))
    flip_confirmation = (
        FlipConfirmationTracker(
            required_sides=confirmation_sides,
            timeframe_ms=15 * 60 * 1000,
        )
        if confirmation_sides
        else None
    )

    for timestamp_ms, directions in sorted(by_timestamp.items()):
        open_positions, newly_closed = close_due_positions(
            open_positions=open_positions,
            timestamp_ms=timestamp_ms,
        )
        closed.extend(newly_closed)
        realized_net_pnl += sum(_float(item.get("net_pnl")) for item in newly_closed)
        long_row = directions.get("LONG")
        short_row = directions.get("SHORT")
        if long_row is None or short_row is None:
            prior_selected_sides.append("NO_SIGNAL")
            if flip_confirmation is not None:
                flip_confirmation.observe(side="NO_SIGNAL", timestamp_ms=timestamp_ms)
            continue
        snapshot = snapshots.at(timestamp_ms)
        if snapshot is None:
            blockers["missing_snapshot"] += 1
            prior_selected_sides.append("NO_SIGNAL")
            if flip_confirmation is not None:
                flip_confirmation.observe(side="NO_SIGNAL", timestamp_ms=timestamp_ms)
            continue
        long_components = adjusted_components(
            profile=long_profile,
            components=long_row["components"],
            snapshot=snapshot,
        )
        short_components = adjusted_components(
            profile=short_profile,
            components=short_row["components"],
            snapshot=snapshot,
        )
        long_score = long_profile.score(long_components)
        short_score = short_profile.score(short_components)
        if long_score >= long_profile.threshold and (
            short_score < short_profile.threshold or long_score >= short_score
        ):
            side, score, source_components = "LONG", long_score, long_components
        elif short_score >= short_profile.threshold and short_score > long_score:
            side, score, source_components = "SHORT", short_score, short_components
        else:
            prior_selected_sides.append("NO_SIGNAL")
            if flip_confirmation is not None:
                flip_confirmation.observe(side="NO_SIGNAL", timestamp_ms=timestamp_ms)
            continue
        selected_counts[side] += 1
        active_profile = long_profile if side == "LONG" else short_profile
        timing_details = timing_context(side=side, prior_sides=prior_selected_sides)
        age = timing_details.direction_signal_age
        timing = timing_details.timing_type
        prior_selected_sides.append(side)
        flip_decision = (
            flip_confirmation.observe(side=side, timestamp_ms=timestamp_ms)
            if flip_confirmation is not None
            else None
        )
        if flip_decision is not None and not flip_decision.allowed:
            blockers[flip_decision.reason] += 1
            continue
        price = float(snapshot.price)
        setup = sl_tp.build_theoretical_setup(
            side=FuturesSignalSide.BUY if side == "LONG" else FuturesSignalSide.SELL,
            entry_price=price,
            snapshot=snapshot,
            confidence=min(1.0, max(0.0, score / 14.6)),
        )
        if setup is None:
            blockers["missing_setup"] += 1
            continue
        exit_levels = adjust_exit_levels(
            profile=active_profile,
            side=side,
            entry=price,
            stop_loss=float(setup.stop_loss),
            take_profit=float(setup.take_profit),
            atr=snapshot.atr,
        )

        same_direction = [position for position in open_positions if position.side == side]
        passed_gate_count = gate_count(side, source_components)
        entry_quality_ok = timing not in {
            str(value).upper() for value in futures_settings.ENTRY_QUALITY_BLOCKED_TIMINGS
        }
        if not entry_quality_ok and side == "SHORT" and timing == "LATE_EXTENSION":
            entry_quality_ok = passed_gate_count >= 2 and score >= 9.0
        location = FuturesEntryLocationClassifier.classify(
            side=side,
            entry_price=price,
            snapshot=snapshot.__dict__,
        )
        long_location_ok = side != "LONG" or str(location.get("type") or "").upper() not in {
            str(value).upper() for value in futures_settings.LONG_ENTRY_BLOCKED_LOCATIONS
        }
        short_plan_ok = side != "SHORT" or short_market_plan_ok(
            entry_price=price,
            plan=plans.get(timestamp_ms),
            timing_type_name=timing,
            passed_gate_count=passed_gate_count,
            score=score,
        )
        features = {
            **entry_features(snapshot=snapshot, side=side),
            **exit_geometry_features(
                entry=price,
                stop_loss=exit_levels.stop_loss,
                take_profit=exit_levels.take_profit,
                atr=snapshot.atr,
            ),
        }
        candidate_policy = evaluate_entry_policy(
            profile=active_profile,
            side=side,
            score=score,
            features=features,
        )
        if not candidate_policy.allowed:
            blockers["candidate_quality_block"] += 1
            continue
        order_margin = float(futures_settings.DEFAULT_ORDER_SIZE_USDT) * float(
            candidate_policy.size_multiplier
        )
        exposure = sum(position.margin for position in open_positions)
        open_entry_fees = sum(position.entry_fee for position in open_positions)
        available = (
            float(futures_settings.DEFAULT_STARTING_BALANCE)
            + realized_net_pnl
            - exposure
            - open_entry_fees
        )
        last_same_direction = (
            max(same_direction, key=lambda position: position.entry_timestamp_ms)
            if same_direction
            else None
        )
        permission = permission_service.evaluate(
            signal_side=side,
            entry_price=price,
            stop_loss=exit_levels.stop_loss,
            leverage=int(futures_settings.DEFAULT_LEVERAGE),
            order_notional_usdt=order_margin,
            available_balance=available,
            current_open_exposure=exposure,
            last_entry_price=last_same_direction.entry if last_same_direction else None,
            cooldown_active=bool(
                last_same_direction
                and timestamp_ms
                < last_same_direction.entry_timestamp_ms
                + int(futures_settings.DEFAULT_COOLDOWN_SECONDS * 1000)
            ),
            duplicate_active=any(abs(position.entry - price) < 0.0001 for position in same_direction),
            entry_quality_ok=entry_quality_ok,
            long_entry_location_ok=long_location_ok,
            short_market_plan_ok=short_plan_ok,
            current_open_positions=len(open_positions),
            current_direction_open_positions=len(same_direction),
        )
        if not permission.allowed:
            blockers[permission.reason] += 1
            continue
        notional = float(order_margin * futures_settings.DEFAULT_LEVERAGE)
        outcome = managed_outcome(
            policy_ids=active_profile.exit_policy_ids,
            candles=candles,
            candle_timestamps=candle_timestamps,
            entry_timestamp_ms=timestamp_ms,
            side=side,
            entry=price,
            stop_loss=exit_levels.stop_loss,
            take_profit=exit_levels.take_profit,
            notional=notional,
            entry_fee_rate=float(futures_settings.ENTRY_FEE_PCT),
            exit_fee_rate=float(futures_settings.EXIT_FEE_PCT),
        )
        if outcome is None:
            blockers["missing_outcome"] += 1
            continue
        outcome = {
            **outcome,
            "score": score,
            "timing_type": timing,
            "prior_actionable_side": timing_details.prior_actionable_side,
            "flip_confirmation_status": (
                flip_decision.status if flip_decision is not None else "NOT_REQUIRED"
            ),
            "gate_count": passed_gate_count,
            "component_scores": source_components,
            "features": features,
            "candidate_policy_reasons": candidate_policy.reasons,
            "exit_policy_applied": exit_levels.applied_policy,
            "exit_policy_reasons": exit_levels.reasons,
            "size_multiplier": candidate_policy.size_multiplier,
            "permission": "allowed",
        }
        opened.append(outcome)
        open_positions.append(
            OpenPosition(
                side=side,
                entry_timestamp_ms=timestamp_ms,
                entry=price,
                margin=order_margin,
                entry_fee=float(notional * futures_settings.ENTRY_FEE_PCT),
                outcome=outcome,
            )
        )

    return {
        "long_profile": long_profile.__dict__,
        "short_profile": short_profile.__dict__,
        "evaluated_timestamps": len(by_timestamp),
        "selected_signals": sum(selected_counts.values()),
        "selected_counts": dict(selected_counts),
        "permission_blockers": dict(blockers.most_common()),
        "exit_policy_applied_count": sum(
            bool(row.get("exit_policy_applied")) for row in opened
        ),
        "portfolio": portfolio_stats(
            opened=opened,
            closed=closed,
            open_positions=open_positions,
            split_timestamp_ms=split_timestamp_ms,
            period_origin_timestamp_ms=period_origin_timestamp_ms,
        ),
        "opened_outcomes": opened,
        "baseline_validation": {
            side: validation(
                (row["entry_timestamp_ms"] for row in opened if row["side"] == side),
                actual_timestamps[side],
            )
            for side in ("LONG", "SHORT")
        },
    }


def _futures_profile_pairs() -> tuple[tuple[CandidateProfile, CandidateProfile], ...]:
    long_baseline = PROFILES["futures_long_baseline_v1"]
    short_baseline = PROFILES["futures_short_baseline_v1"]
    return (
        (long_baseline, short_baseline),
        (PROFILES["futures_long_profit_lock_70_25_v1"], short_baseline),
        (PROFILES["futures_long_flip_confirmation_v1"], short_baseline),
        (long_baseline, PROFILES["futures_short_flip_confirmation_v1"]),
        (long_baseline, PROFILES["futures_short_mid_stop_cap_25_v1"]),
        (long_baseline, PROFILES["futures_short_mid_stop_floor_35_v1"]),
        (long_baseline, PROFILES["futures_short_rr_20_22_target_18_v1"]),
        (long_baseline, PROFILES["futures_short_flip_stop_cap_25_v1"]),
        (
            PROFILES["futures_long_macd_spread_02_05_neutral_v1"],
            PROFILES["futures_short_flip_stop_cap_25_v1"],
        ),
        (
            PROFILES["futures_long_flip_confirmation_v1"],
            PROFILES["futures_short_flip_confirmation_v1"],
        ),
        (PROFILES["futures_long_mtf_half_v1"], short_baseline),
        (PROFILES["futures_long_mtf_075_v1"], short_baseline),
        (PROFILES["futures_long_rsi_momentum_disabled_v1"], short_baseline),
        (PROFILES["futures_long_rsi_momentum_pullback_v1"], short_baseline),
        (PROFILES["futures_long_rsi_58_65_neutral_v1"], short_baseline),
        (PROFILES["futures_long_rsi_58_65_half_reward_v1"], short_baseline),
        (PROFILES["futures_long_macd_alignment_neutral_v1"], short_baseline),
        (PROFILES["futures_long_macd_alignment_half_reward_v1"], short_baseline),
        (PROFILES["futures_long_macd_spread_02_05_neutral_v1"], short_baseline),
        (PROFILES["futures_long_macd_neutral_atr_growth_v1"], short_baseline),
        (PROFILES["futures_long_macd_neutral_rsi55_v1"], short_baseline),
        (PROFILES["futures_long_macd_neutral_rsi58_v1"], short_baseline),
        (PROFILES["futures_long_macd_neutral_rsi60_v1"], short_baseline),
        (PROFILES["futures_long_macd_neutral_rsi65_v1"], short_baseline),
        (PROFILES["futures_long_mtf_half_macd_neutral_rsi58_v1"], short_baseline),
        (PROFILES["futures_long_mtf075_macd_half_v1"], short_baseline),
        (PROFILES["futures_long_rsi_macd_neutral_v1"], short_baseline),
        (long_baseline, PROFILES["futures_short_momentum_zero_v1"]),
        (long_baseline, PROFILES["futures_short_trend_half_t95_v1"]),
        (long_baseline, PROFILES["futures_short_structure_half_t10_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_neutral_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_threshold10_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_threshold105_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_half_size_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_size075_v1"]),
        (long_baseline, PROFILES["futures_short_macd_0_02_size025_v1"]),
        (long_baseline, PROFILES["futures_short_structure_15_25_neutral_v1"]),
        (long_baseline, PROFILES["futures_short_di_alignment_neutral_v1"]),
        (long_baseline, PROFILES["futures_short_top3_neutral_v1"]),
        (
            PROFILES["futures_long_macd_neutral_rsi58_v1"],
            PROFILES["futures_short_macd_0_02_size025_v1"],
        ),
    )


def build_report(
    snapshot_root: Path,
    *,
    repair_macd_histogram: bool = False,
    evaluation_start_ms: int | None = None,
    spot_profiles: tuple[CandidateProfile, ...] | None = None,
    futures_profile_pairs: tuple[tuple[CandidateProfile, CandidateProfile], ...] | None = None,
) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    actual = actual_open_timestamps(roots)
    if evaluation_start_ms is not None:
        actual = {
            side: [timestamp for timestamp in timestamps if timestamp > evaluation_start_ms]
            for side, timestamps in actual.items()
        }
    actual_performance = actual_closed_performance(
        roots,
        evaluation_start_ms=evaluation_start_ms,
    )
    spot_rows = _reconstruct_spot(roots.spot, repair_macd_histogram=repair_macd_histogram)
    futures_rows = _reconstruct_futures(roots.futures, repair_macd_histogram=repair_macd_histogram)
    if evaluation_start_ms is not None:
        spot_rows = [row for row in spot_rows if int(row["timestamp_ms"]) > evaluation_start_ms]
        futures_rows = [row for row in futures_rows if int(row["timestamp_ms"]) > evaluation_start_ms]
    if not spot_rows or not futures_rows:
        raise ValueError("No replay decision rows exist after the requested evaluation cutoff.")
    futures_by_timestamp: dict[int, dict[str, dict[str, Any]]] = {}
    for row in futures_rows:
        futures_by_timestamp.setdefault(int(row["timestamp_ms"]), {})[str(row["side"])] = row

    spot_snapshots = _indicator_index(
        roots.spot / "indicator_snapshots" / "BTCUSDT" / "15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=SpotIndicatorRepository._parse_snapshot_row,
        repair_macd_histogram=repair_macd_histogram,
    )
    futures_snapshots = _indicator_index(
        roots.futures / "indicator_snapshots_futures" / "BTCUSDT" / "indicators_15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=FuturesIndicatorRepository._parse_snapshot_row,
        repair_macd_histogram=repair_macd_histogram,
    )
    spot_candles = _candle_rows(roots.spot / "candles" / "BTCUSDT" / "5m.json")
    futures_candles = _candle_rows(
        roots.futures / "candles_futures" / "BTCUSDT" / "candles_5m.json"
    )
    plans = {
        int(row.get("timestamp_ms") or 0): row
        for row in load_family_rows(roots.futures / "futures_market_plans")
        if int(row.get("timestamp_ms") or 0) > 0
    }

    selected_spot_profiles = spot_profiles or tuple(
        PROFILES[profile_id]
        for profile_id in ("spot_baseline_v1", "spot_orderbook_zero_v1")
    )
    spot_reports = {
        profile.profile_id: _spot_profile_replay(
            profile=profile,
            rows=spot_rows,
            snapshots=spot_snapshots,
            candles=spot_candles,
            actual_timestamps=actual["SPOT"],
            split_timestamp_ms=int(spot_rows[len(spot_rows) // 2]["timestamp_ms"]),
            period_origin_timestamp_ms=int(spot_rows[0]["timestamp_ms"]),
        )
        for profile in selected_spot_profiles
    }
    futures_reports: dict[str, Any] = {}
    futures_timestamps = sorted(futures_by_timestamp)
    for long_profile, short_profile in futures_profile_pairs or _futures_profile_pairs():
        pair_id = f"{long_profile.profile_id}__{short_profile.profile_id}"
        futures_reports[pair_id] = _futures_profile_replay(
            long_profile=long_profile,
            short_profile=short_profile,
            by_timestamp=futures_by_timestamp,
            snapshots=futures_snapshots,
            candles=futures_candles,
            plans=plans,
            actual_timestamps={"LONG": actual["LONG"], "SHORT": actual["SHORT"]},
            split_timestamp_ms=int(sorted(futures_by_timestamp)[len(futures_by_timestamp) // 2]),
            period_origin_timestamp_ms=int(futures_timestamps[0]),
        )
    futures_baseline = futures_reports[
        "futures_long_baseline_v1__futures_short_baseline_v1"
    ]
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "permission_state_aware_portfolio_replay_v1",
        "macd_histogram_repaired": repair_macd_histogram,
        "evaluation_start_ms_exclusive": evaluation_start_ms,
        "exit_timeframe": "5m",
        "modeled_permissions": {
            "spot": [
                "capital", "exposure", "duplicate", "cooldown", "proximity",
                "weak_open_position", "buy_entry_location",
            ],
            "futures": [
                "capital", "exposure", "position_slots", "direction_position_slots",
                "liquidation_buffer", "entry_quality", "long_entry_location",
                "short_market_plan_zone", "duplicate", "cooldown", "proximity",
            ],
        },
        "limitations": [
            "Historical component scores are reconstructed under current code where persisted components are unavailable.",
            "Spot minus-rule force closes are modeled at decision checkpoints using the latest closed 5m candle.",
            "Intra-candle ordering beyond conservative SL-first handling is not modeled.",
            "Exact timestamp validation measures fidelity; candidate PnL must not be treated as live performance until fidelity is acceptable.",
            *(
                [
                    "Post-cutoff evaluation starts an independent flat shadow portfolio; positions and reserved capital opened before the cutoff are not inherited."
                ]
                if evaluation_start_ms is not None
                else []
            ),
        ],
        "actual_open_counts": {key: len(value) for key, value in actual.items()},
        "actual_closed_performance": actual_performance,
        "futures_market_context_7d": build_market_context_7d(
            snapshots=futures_snapshots,
            timestamps=futures_timestamps,
            origin_timestamp_ms=int(futures_timestamps[0]),
        ),
        "baseline_outcome_audit": build_outcome_audit(
            futures_baseline["opened_outcomes"],
            split_timestamp_ms=int(futures_timestamps[len(futures_timestamps) // 2]),
        ),
        "spot": spot_reports,
        "futures": futures_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay candidate profiles with portfolio state.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    parser.add_argument("--repair-macd-histogram", action="store_true")
    parser.add_argument("--evaluation-start-ms", type=int)
    args = parser.parse_args()
    report = build_report(
        args.snapshot,
        repair_macd_histogram=bool(args.repair_macd_histogram),
        evaluation_start_ms=args.evaluation_start_ms,
    )
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
