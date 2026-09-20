"""Documentation/code comparison capability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platform_v2.futures.config import settings as futures_settings
from platform_v2.spot.config import settings as spot_settings
from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT

from .contracts import CapabilityAnswer


RISK_DOC = REPO_ROOT / "platform_v2" / "docs" / "trading" / "risk_and_permissions.md"
FUTURES_DOC = REPO_ROOT / "platform_v2" / "docs" / "trading" / "futures_rules.md"
FUTURES_PERMISSION_CODE = (
    REPO_ROOT
    / "platform_v2"
    / "futures"
    / "services"
    / "permission"
    / "futures_permission_decision_service.py"
)
SPOT_PERMISSION_CODE = (
    REPO_ROOT / "platform_v2" / "spot" / "services" / "permission" / "permission_decision_service.py"
)
SPOT_EXECUTION_MODEL = REPO_ROOT / "platform_v2" / "spot" / "domain" / "models" / "execution.py"
FUTURES_SIGNAL_CODE = (
    REPO_ROOT
    / "platform_v2"
    / "futures"
    / "services"
    / "signal"
    / "futures_signal_decision_service.py"
)
SL_TP_DOC = REPO_ROOT / "platform_v2" / "docs" / "trading" / "sl_tp_policy.md"
FUTURES_SL_TP_SERVICE = (
    REPO_ROOT / "platform_v2" / "futures" / "services" / "trading" / "futures_sl_tp_service.py"
)
FUTURES_STOP_LOSS_CODE = REPO_ROOT / "platform_v2" / "futures" / "domain" / "models" / "stop_loss.py"
FUTURES_TAKE_PROFIT_CODE = REPO_ROOT / "platform_v2" / "futures" / "domain" / "models" / "take_profit.py"
SPOT_SL_TP_SERVICE = REPO_ROOT / "platform_v2" / "spot" / "services" / "trading" / "sl_tp_service.py"
SPOT_STOP_LOSS_CODE = REPO_ROOT / "platform_v2" / "spot" / "domain" / "models" / "stop_loss.py"
SPOT_TAKE_PROFIT_CODE = REPO_ROOT / "platform_v2" / "spot" / "domain" / "models" / "take_profit.py"


FUTURES_PERMISSION_CHECKS = (
    "signal_is_actionable",
    "manual_block",
    "capital",
    "exposure",
    "position_slots",
    "direction_position_slots",
    "liquidation_buffer",
    "duplicate",
    "cooldown",
    "proximity",
    "weak_open_position",
    "entry_quality",
    "long_entry_location",
    "short_market_plan_zone",
)

FUTURES_REASON_PRIORITY = (
    "signal_block",
    "manual_block",
    "capital_block",
    "exposure_block",
    "position_slots_block",
    "direction_position_slots_block",
    "liquidation_buffer_block",
    "entry_quality_block",
    "long_entry_location_block",
    "short_market_plan_zone_block",
    "duplicate_block",
    "cooldown_block",
    "proximity_block",
    "weak_open_position_block",
    "allowed",
)

SPOT_PERMISSION_CHECKS = (
    "signal_is_actionable",
    "manual_block",
    "capital",
    "exposure",
    "duplicate",
    "cooldown",
    "proximity",
    "weak_open_position",
    "buy_entry_location",
)

SPOT_REASONS = (
    "unknown",
    "manual_block",
    "capital_block",
    "exposure_block",
    "duplicate_block",
    "cooldown_block",
    "proximity_block",
    "weak_open_position_block",
    "buy_entry_location_block",
    "allowed",
)


@dataclass(frozen=True)
class CompareFinding:
    severity: str
    title: str
    detail: str


def answer_docs_compare() -> CapabilityAnswer:
    findings: list[CompareFinding] = []
    findings.extend(_compare_token_list("Futures permission checks", FUTURES_PERMISSION_CHECKS, RISK_DOC, FUTURES_PERMISSION_CODE))
    findings.extend(_compare_token_list("Futures reason priority", FUTURES_REASON_PRIORITY, RISK_DOC, FUTURES_PERMISSION_CODE))
    findings.extend(_compare_token_list("Spot permission checks", SPOT_PERMISSION_CHECKS, RISK_DOC, SPOT_PERMISSION_CODE))
    findings.extend(_compare_token_list("Spot block reasons", SPOT_REASONS, RISK_DOC, SPOT_EXECUTION_MODEL))
    findings.extend(_compare_futures_signal_numbers())
    findings.extend(_compare_sl_tp_policy())

    high = sum(1 for finding in findings if finding.severity == "HIGH")
    medium = sum(1 for finding in findings if finding.severity == "MEDIUM")
    low = sum(1 for finding in findings if finding.severity == "LOW")

    lines = [
        "Docs/code comparison",
        f"Findings: {len(findings)} total, HIGH={high}, MEDIUM={medium}, LOW={low}",
        "Checked categories:",
        "- Futures permission checks and reason priority",
        "- Spot permission checks and denial reasons",
        "- Futures signal threshold, weights, and raw gate minimums",
        "- Spot/Futures adaptive SL/TP service shape",
        "- Stop-loss source priority, distance limits, ADX adjustment, and fee buffer",
        "- Take-profit base RRR and clamp labels",
    ]
    if not findings:
        lines.append("No checked mismatch found in the current targeted audit.")
    else:
        for finding in findings[:12]:
            lines.append(f"- {finding.severity}: {finding.title} - {finding.detail}")
    lines.extend(
        [
            "Checked targets:",
            f"- {RISK_DOC}",
            f"- {FUTURES_DOC}",
            f"- {FUTURES_PERMISSION_CODE}",
            f"- {SPOT_PERMISSION_CODE}",
            f"- {SPOT_EXECUTION_MODEL}",
            f"- {FUTURES_SIGNAL_CODE}",
            f"- {SL_TP_DOC}",
            f"- {FUTURES_SL_TP_SERVICE}",
            f"- {FUTURES_STOP_LOSS_CODE}",
            f"- {FUTURES_TAKE_PROFIT_CODE}",
            f"- {SPOT_SL_TP_SERVICE}",
            f"- {SPOT_STOP_LOSS_CODE}",
            f"- {SPOT_TAKE_PROFIT_CODE}",
        ]
    )
    return CapabilityAnswer(
        "docs_compare",
        "\n".join(lines),
        tuple(
            str(path)
            for path in (
                RISK_DOC,
                FUTURES_DOC,
                FUTURES_PERMISSION_CODE,
                SPOT_PERMISSION_CODE,
                SPOT_EXECUTION_MODEL,
                FUTURES_SIGNAL_CODE,
                SL_TP_DOC,
                FUTURES_SL_TP_SERVICE,
                FUTURES_STOP_LOSS_CODE,
                FUTURES_TAKE_PROFIT_CODE,
                SPOT_SL_TP_SERVICE,
                SPOT_STOP_LOSS_CODE,
                SPOT_TAKE_PROFIT_CODE,
            )
        ),
        {"findings_total": len(findings), "high": high, "medium": medium, "low": low},
    )


def _compare_token_list(
    title: str,
    expected_tokens: tuple[str, ...],
    doc_path: Path,
    code_path: Path,
) -> list[CompareFinding]:
    doc_text = _read(doc_path)
    code_text = _read(code_path)
    findings: list[CompareFinding] = []
    missing_in_doc = [token for token in expected_tokens if token not in doc_text]
    missing_in_code = [token for token in expected_tokens if token not in code_text]
    if missing_in_doc:
        findings.append(
            CompareFinding(
                "MEDIUM",
                f"{title}: docs missing tokens",
                ", ".join(missing_in_doc),
            )
        )
    if missing_in_code:
        findings.append(
            CompareFinding(
                "HIGH",
                f"{title}: code missing tokens",
                ", ".join(missing_in_code),
            )
        )
    return findings


def _compare_sl_tp_policy() -> list[CompareFinding]:
    doc_text = _read(SL_TP_DOC)
    futures_service = _read(FUTURES_SL_TP_SERVICE)
    spot_service = _read(SPOT_SL_TP_SERVICE)
    futures_sl = _read(FUTURES_STOP_LOSS_CODE)
    futures_tp = _read(FUTURES_TAKE_PROFIT_CODE)
    spot_sl = _read(SPOT_STOP_LOSS_CODE)
    spot_tp = _read(SPOT_TAKE_PROFIT_CODE)
    findings: list[CompareFinding] = []

    required_doc_tokens = (
        "adaptive",
        "ATR",
        "swing",
        "kijun",
        "ema50",
        "3.5",
        "2.6",
        "2.0",
        "ADX < 18",
        "ADX > 28",
        "0.0006",
        "resistance_level",
        "liquidity_zone",
        "psychological level",
    )
    missing_doc = [token for token in required_doc_tokens if token not in doc_text]
    if missing_doc:
        findings.append(
            CompareFinding(
                "MEDIUM",
                "SL/TP policy doc missing expected policy tokens",
                ", ".join(missing_doc),
            )
        )

    for title, service_text in (("Futures SL/TP service", futures_service), ("Spot SL/TP service", spot_service)):
        for token in ("compute_stop_loss", "compute_take_profit", "fee_buffer_pct=0.0006", "mode=\"adaptive_v2\""):
            if token not in service_text:
                findings.append(CompareFinding("HIGH", f"{title} missing token", token))

    for title, sl_text in (("Futures stop-loss code", futures_sl), ("Spot stop-loss code", spot_sl)):
        for token in ('("swing"', '("kijun"', '("ema50"', "3.5", "2.6", "2.0", "adxv < 18", "adxv > 28"):
            if token not in sl_text:
                findings.append(CompareFinding("HIGH", f"{title} missing stop-loss policy token", token))

    for title, tp_text in (("Futures take-profit code", futures_tp), ("Spot take-profit code", spot_tp)):
        for token in ("base_rrr", "resistance_level", "liquidity_zone", "psych_level", "expanded_rrr"):
            if token not in tp_text:
                findings.append(CompareFinding("HIGH", f"{title} missing take-profit policy token", token))

    return findings


def _compare_futures_signal_numbers() -> list[CompareFinding]:
    doc_text = _read(FUTURES_DOC)
    code_text = _read(FUTURES_SIGNAL_CODE)
    findings: list[CompareFinding] = []
    expected_values: dict[str, Any] = {
        "BUY_THRESHOLD": futures_settings.BUY_THRESHOLD,
        "MTF_WEIGHT": futures_settings.MTF_WEIGHT,
        "REGIME_WEIGHT": futures_settings.REGIME_WEIGHT,
        "TREND_WEIGHT": futures_settings.TREND_WEIGHT,
        "MOMENTUM_WEIGHT": futures_settings.MOMENTUM_WEIGHT,
        "ORDERBOOK_WEIGHT": futures_settings.ORDERBOOK_WEIGHT,
        "STRUCTURE_WEIGHT": futures_settings.STRUCTURE_WEIGHT,
        "MTF_RAW_GATE_MIN": futures_settings.MTF_RAW_GATE_MIN,
        "REGIME_RAW_GATE_MIN": futures_settings.REGIME_RAW_GATE_MIN,
        "TREND_RAW_MIN": futures_settings.TREND_RAW_MIN,
        "MOMENTUM_RAW_GATE_MIN": futures_settings.MOMENTUM_RAW_GATE_MIN,
        "SHORT_MOMENTUM_RAW_GATE_MIN": futures_settings.SHORT_MOMENTUM_RAW_GATE_MIN,
        "ORDERBOOK_RAW_GATE_MIN": futures_settings.ORDERBOOK_RAW_GATE_MIN,
        "STRUCTURE_RAW_GATE_MIN": futures_settings.STRUCTURE_RAW_GATE_MIN,
        "LONG_STRUCTURE_RAW_GATE_MIN": futures_settings.LONG_STRUCTURE_RAW_GATE_MIN,
        "SHORT_STRUCTURE_RAW_GATE_MIN": futures_settings.SHORT_STRUCTURE_RAW_GATE_MIN,
    }
    for name, value in expected_values.items():
        value_text = _format_number(value)
        if value_text not in doc_text:
            findings.append(
                CompareFinding(
                    "MEDIUM",
                    f"Futures rules doc missing setting value",
                    f"{name}={value_text}",
                )
            )
    if "settings.BUY_THRESHOLD" not in code_text:
        findings.append(
            CompareFinding(
                "HIGH",
                "Futures signal code threshold lookup",
                "settings.BUY_THRESHOLD not found in signal decision code",
            )
        )
    if spot_settings.BUY_THRESHOLD != futures_settings.BUY_THRESHOLD:
        findings.append(
            CompareFinding(
                "LOW",
                "Spot/Futures BUY threshold differs",
                f"spot={spot_settings.BUY_THRESHOLD}, futures={futures_settings.BUY_THRESHOLD}",
            )
        )
    return findings


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _format_number(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)
