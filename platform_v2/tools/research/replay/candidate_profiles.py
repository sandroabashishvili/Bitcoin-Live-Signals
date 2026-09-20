"""Versioned, research-only strategy candidate profiles.

Profiles in this module never alter live settings. They make every tested
weight/threshold combination explicit and reproducible for replay and shadow
evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.futures.config import settings as futures_settings
from platform_v2.spot.config import settings as spot_settings


COMPONENTS = ("mtf", "regime", "trend", "momentum", "orderbook", "structure")


@dataclass(frozen=True)
class CandidateProfile:
    profile_id: str
    market: str
    direction: str
    strategy_version: str
    threshold: float
    weights: dict[str, float]
    status: str
    rationale: str
    adjustment_ids: tuple[str, ...] = ()
    permission_policy_ids: tuple[str, ...] = ()
    exit_policy_ids: tuple[str, ...] = ()

    def score(self, components: dict[str, float]) -> float:
        return round(
            sum(float(components.get(name, 0.0)) * float(self.weights.get(name, 0.0)) for name in COMPONENTS),
            2,
        )


def _weights(source: dict[str, float], **overrides: float) -> dict[str, float]:
    result = {name: float(source[name]) for name in COMPONENTS}
    result.update({name: float(value) for name, value in overrides.items()})
    return result


PROFILES: dict[str, CandidateProfile] = {
    "spot_baseline_v1": CandidateProfile(
        profile_id="spot_baseline_v1",
        market="spot",
        direction="BUY",
        strategy_version=spot_settings.STRATEGY_VERSION,
        threshold=float(spot_settings.BUY_THRESHOLD),
        weights=_weights(spot_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="baseline",
        rationale="Current Spot scoring baseline.",
    ),
    "spot_orderbook_zero_v1": CandidateProfile(
        profile_id="spot_orderbook_zero_v1",
        market="spot",
        direction="BUY",
        strategy_version="research-spot-orderbook-zero-v1",
        threshold=8.5,
        weights=_weights(spot_settings.SIGNAL_COMPONENT_WEIGHTS, orderbook=0.0),
        status="replay_candidate",
        rationale="Spot orderflow reward bands were negative in both chronological segments.",
    ),
    "futures_long_baseline_v1": CandidateProfile(
        profile_id="futures_long_baseline_v1",
        market="futures",
        direction="LONG",
        strategy_version="futures-baseline-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="baseline",
        rationale="Current Futures LONG scoring baseline.",
    ),
    "futures_long_flip_confirmation_v1": CandidateProfile(
        profile_id="futures_long_flip_confirmation_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-flip-confirmation-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Require a true LONG direction flip to persist through the next closed 15m candle.",
        permission_policy_ids=("true_flip_one_candle_confirmation",),
    ),
    "futures_long_profit_lock_70_25_v1": CandidateProfile(
        profile_id="futures_long_profit_lock_70_25_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-profit-lock-70-25-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale=(
            "After LONG reaches 70% of its TP path, protect 25% of the original "
            "reward from the next closed 5m candle."
        ),
        exit_policy_ids=("long_profit_lock_70_25",),
    ),
    "futures_long_mtf_half_v1": CandidateProfile(
        profile_id="futures_long_mtf_half_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-mtf-half-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, mtf=0.5),
        status="replay_candidate",
        rationale="MTF half-weight retained a positive train and test cohort.",
    ),
    "futures_long_mtf_075_v1": CandidateProfile(
        profile_id="futures_long_mtf_075_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-mtf-075-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, mtf=0.75),
        status="replay_candidate",
        rationale="Calibrate MTF influence between the 1.0 baseline and 0.5 boundary candidate.",
    ),
    "futures_long_rsi_momentum_disabled_v1": CandidateProfile(
        profile_id="futures_long_rsi_momentum_disabled_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-rsi-momentum-disabled-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Keep RSI in MTF entry context but remove its duplicate Momentum reward.",
        adjustment_ids=("long_rsi_momentum_disabled",),
    ),
    "futures_long_rsi_momentum_pullback_v1": CandidateProfile(
        profile_id="futures_long_rsi_momentum_pullback_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-rsi-momentum-pullback-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Replace the late Momentum RSI reward with the existing MTF pullback map.",
        adjustment_ids=("long_rsi_momentum_pullback_map",),
    ),
    "futures_long_rsi_58_65_neutral_v1": CandidateProfile(
        profile_id="futures_long_rsi_58_65_neutral_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-rsi-58-65-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the current +1.4 LONG momentum reward in the RSI 58-65 band.",
        adjustment_ids=("long_rsi_58_65_reward_zero",),
    ),
    "futures_long_rsi_58_65_half_reward_v1": CandidateProfile(
        profile_id="futures_long_rsi_58_65_half_reward_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-rsi-58-65-half-reward-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Reduce the RSI 58-65 reward from +1.4 to +0.7 instead of removing it.",
        adjustment_ids=("long_rsi_58_65_reward_half",),
    ),
    "futures_long_macd_alignment_neutral_v1": CandidateProfile(
        profile_id="futures_long_macd_alignment_neutral_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-alignment-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the current +0.8 LONG momentum reward for MACD above signal.",
        adjustment_ids=("long_macd_alignment_reward_zero",),
    ),
    "futures_long_macd_alignment_half_reward_v1": CandidateProfile(
        profile_id="futures_long_macd_alignment_half_reward_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-alignment-half-reward-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Reduce the LONG MACD alignment reward from +0.8 to +0.4.",
        adjustment_ids=("long_macd_alignment_reward_half",),
    ),
    "futures_long_macd_spread_02_05_neutral_v1": CandidateProfile(
        profile_id="futures_long_macd_spread_02_05_neutral_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-spread-02-05-neutral-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the MACD alignment reward at 0.2-0.5 ATR spread.",
        adjustment_ids=("long_macd_spread_02_05_reward_zero",),
    ),
    "futures_long_macd_neutral_atr_growth_v1": CandidateProfile(
        profile_id="futures_long_macd_neutral_atr_growth_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-neutral-atr-growth-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove MACD alignment reward only while ATR growth is at least 0.05.",
        adjustment_ids=("long_macd_alignment_zero_when_atr_growth_005",),
    ),
    "futures_long_macd_neutral_rsi58_v1": CandidateProfile(
        profile_id="futures_long_macd_neutral_rsi58_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-neutral-rsi58-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove MACD alignment reward only when RSI is already 58 or higher.",
        adjustment_ids=("long_macd_alignment_zero_when_rsi_58",),
    ),
    "futures_long_macd_neutral_rsi55_v1": CandidateProfile(
        profile_id="futures_long_macd_neutral_rsi55_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-neutral-rsi55-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove MACD alignment reward when RSI is already 55 or higher.",
        adjustment_ids=("long_macd_alignment_zero_when_rsi_55",),
    ),
    "futures_long_macd_neutral_rsi60_v1": CandidateProfile(
        profile_id="futures_long_macd_neutral_rsi60_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-neutral-rsi60-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove MACD alignment reward when RSI is already 60 or higher.",
        adjustment_ids=("long_macd_alignment_zero_when_rsi_60",),
    ),
    "futures_long_macd_neutral_rsi65_v1": CandidateProfile(
        profile_id="futures_long_macd_neutral_rsi65_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-macd-neutral-rsi65-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove MACD alignment reward only when RSI is 65 or higher.",
        adjustment_ids=("long_macd_alignment_zero_when_rsi_65",),
    ),
    "futures_long_mtf_half_macd_neutral_rsi58_v1": CandidateProfile(
        profile_id="futures_long_mtf_half_macd_neutral_rsi58_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-mtf-half-macd-neutral-rsi58-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, mtf=0.5),
        status="replay_candidate",
        rationale="Final controlled combination: MTF half-weight plus late-RSI-only MACD reward removal.",
        adjustment_ids=("long_macd_alignment_zero_when_rsi_58",),
    ),
    "futures_long_mtf075_macd_half_v1": CandidateProfile(
        profile_id="futures_long_mtf075_macd_half_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-mtf075-macd-half-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, mtf=0.75),
        status="replay_candidate",
        rationale="Combine moderate MTF and MACD calibration without disabling either input.",
        adjustment_ids=("long_macd_alignment_reward_half",),
    ),
    "futures_long_rsi_macd_neutral_v1": CandidateProfile(
        profile_id="futures_long_rsi_macd_neutral_v1",
        market="futures",
        direction="LONG",
        strategy_version="research-futures-long-rsi-macd-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove the two stable-negative LONG momentum rewards together.",
        adjustment_ids=("long_rsi_58_65_reward_zero", "long_macd_alignment_reward_zero"),
    ),
    "futures_short_baseline_v1": CandidateProfile(
        profile_id="futures_short_baseline_v1",
        market="futures",
        direction="SHORT",
        strategy_version="futures-baseline-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="baseline",
        rationale="Current Futures SHORT scoring baseline.",
    ),
    "futures_short_flip_confirmation_v1": CandidateProfile(
        profile_id="futures_short_flip_confirmation_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-flip-confirmation-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Require a true SHORT direction flip to persist through the next closed 15m candle.",
        permission_policy_ids=("true_flip_one_candle_confirmation",),
    ),
    "futures_short_mid_stop_cap_25_v1": CandidateProfile(
        profile_id="futures_short_mid_stop_cap_25_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-mid-stop-cap-25-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Tighten only 2.5-3.5 ATR SHORT stops to 2.5 ATR; keep TP unchanged.",
        exit_policy_ids=("short_mid_stop_cap_25_atr",),
    ),
    "futures_short_mid_stop_floor_35_v1": CandidateProfile(
        profile_id="futures_short_mid_stop_floor_35_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-mid-stop-floor-35-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Widen only 2.5-3.5 ATR SHORT stops to 3.5 ATR; keep TP unchanged.",
        exit_policy_ids=("short_mid_stop_floor_35_atr",),
    ),
    "futures_short_rr_20_22_target_18_v1": CandidateProfile(
        profile_id="futures_short_rr_20_22_target_18_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-rr-20-22-target-18-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Move only SHORT 2.0-2.2 R targets to 1.8 R; keep SL unchanged.",
        exit_policy_ids=("short_rr_20_22_target_18",),
    ),
    "futures_short_flip_stop_cap_25_v1": CandidateProfile(
        profile_id="futures_short_flip_stop_cap_25_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-flip-stop-cap-25-v1",
        threshold=float(futures_settings.BUY_THRESHOLD),
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale=(
            "Combine one-candle true-flip confirmation with the 2.5 ATR cap "
            "for baseline SHORT stops in the 2.5-3.5 ATR band."
        ),
        permission_policy_ids=("true_flip_one_candle_confirmation",),
        exit_policy_ids=("short_mid_stop_cap_25_atr",),
    ),
    "futures_short_momentum_zero_v1": CandidateProfile(
        profile_id="futures_short_momentum_zero_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-momentum-zero-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, momentum=0.0),
        status="replay_candidate",
        rationale="Current SHORT momentum reward retained losses; zero is a boundary test, not a live decision.",
    ),
    "futures_short_trend_half_t95_v1": CandidateProfile(
        profile_id="futures_short_trend_half_t95_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-trend-half-t95-v1",
        threshold=9.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, trend=0.65),
        status="replay_candidate",
        rationale="Trend alignment appears late for SHORT; half weight with 9.5 threshold was stable in retention tests.",
    ),
    "futures_short_structure_half_t10_v1": CandidateProfile(
        profile_id="futures_short_structure_half_t10_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-structure-half-t10-v1",
        threshold=10.0,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS, structure=0.45),
        status="replay_candidate",
        rationale="Current rewarded SHORT structure bands were strongly negative in both time segments.",
    ),
    "futures_short_macd_0_02_neutral_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_neutral_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the +0.9 SHORT momentum reward for directional MACD spread 0-0.2 ATR.",
        adjustment_ids=("short_macd_spread_0_02_reward_zero",),
    ),
    "futures_short_macd_0_02_threshold10_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_threshold10_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-threshold10-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Keep the signal reward but require score 10.0 in the weak 0-0.2 ATR MACD-spread cohort.",
        permission_policy_ids=("short_macd_0_02_min_score_10",),
    ),
    "futures_short_macd_0_02_threshold105_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_threshold105_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-threshold105-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Keep the signal reward but require score 10.5 in the weak 0-0.2 ATR MACD-spread cohort.",
        permission_policy_ids=("short_macd_0_02_min_score_105",),
    ),
    "futures_short_macd_0_02_half_size_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_half_size_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-half-size-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Keep eligible SHORT entries but use half margin/notional in the weak MACD-spread cohort.",
        permission_policy_ids=("short_macd_0_02_half_size",),
    ),
    "futures_short_macd_0_02_size075_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_size075_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-size075-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Use 75% size in the weak SHORT MACD-spread cohort.",
        permission_policy_ids=("short_macd_0_02_size_075",),
    ),
    "futures_short_macd_0_02_size025_v1": CandidateProfile(
        profile_id="futures_short_macd_0_02_size025_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-macd-0-02-size025-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Use 25% size in the weak SHORT MACD-spread cohort.",
        permission_policy_ids=("short_macd_0_02_size_025",),
    ),
    "futures_short_structure_15_25_neutral_v1": CandidateProfile(
        profile_id="futures_short_structure_15_25_neutral_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-structure-15-25-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the +1.3 SHORT structure reward at 1.5-2.5 ATR from swing high.",
        adjustment_ids=("short_structure_distance_15_25_reward_zero",),
    ),
    "futures_short_di_alignment_neutral_v1": CandidateProfile(
        profile_id="futures_short_di_alignment_neutral_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-di-alignment-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Remove only the +1.0 SHORT trend reward for bearish DI alignment with ADX confirmation.",
        adjustment_ids=("short_di_alignment_reward_zero",),
    ),
    "futures_short_top3_neutral_v1": CandidateProfile(
        profile_id="futures_short_top3_neutral_v1",
        market="futures",
        direction="SHORT",
        strategy_version="research-futures-short-top3-neutral-v1",
        threshold=8.5,
        weights=_weights(futures_settings.SIGNAL_COMPONENT_WEIGHTS),
        status="replay_candidate",
        rationale="Combine the three stable-negative SHORT reward removals without disabling whole components.",
        adjustment_ids=(
            "short_macd_spread_0_02_reward_zero",
            "short_structure_distance_15_25_reward_zero",
            "short_di_alignment_reward_zero",
        ),
    ),
}


def profiles_for(*, market: str, direction: str) -> tuple[CandidateProfile, ...]:
    return tuple(
        profile
        for profile in PROFILES.values()
        if profile.market == market and profile.direction == direction
    )
