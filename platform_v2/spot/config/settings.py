"""File: settings.py
Folder: platform_v2/spot/config
Created date: 2026-03-25
Last updated date: 2026-06-01
Author: Codex
Purpose: Central runtime and strategy defaults for SmartSignalHub V2.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOTENV_PATH = PROJECT_ROOT / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(DOTENV_PATH)


# საბაზისო სიმბოლო და სამუშაო ტაიმფრეიმები
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_TIMEFRAME = "15m"
# 1m is execution monitoring only; strategy indicators remain 5m/15m/4h.
DEFAULT_FETCH_TIMEFRAMES = ("1m", "5m", "15m", "4h")
DEFAULT_CANDLE_TIMEFRAMES = ("5m", "15m", "4h")
# თითო fetch-ზე რამდენი სანთელი წამოვიღოთ მაქსიმუმ
DEFAULT_FETCH_LIMIT = 500
# მხოლოდ სპოტ-ლოგიკაზე მუშაობს, short/futures რეჟიმის გარეშე
SPOT_ONLY_MODE = True

# პორტფელის და პოზიციის საწყისი პარამეტრები
DEFAULT_POSITION_SIZE = 100.0
DEFAULT_STARTING_BALANCE = 3000.0
ENTRY_FEE_PCT = 0.0005
EXIT_FEE_PCT = 0.0005
# Position state is cumulative. None means read every available daily ledger.
DEFAULT_LOOKBACK_DAYS: int | None = None
# ერთ სერიაში სამუშაოდ რამდენი candle გვქონდეს ხელმისაწვდომი მაქსიმუმ
DEFAULT_CANDLE_LIMIT = 200

# სიგნალის ძირითადი thresholds და market regime ფილტრები
# BUY სიგნალის გასასვლელი მინიმალური ქულა
BUY_THRESHOLD = 8.5
STRATEGY_VERSION = "spot-independent-direction-quality-v5"
# Persist the real histogram history, but do not reward its sequence in live
# scoring until the repaired behavior passes portfolio replay and shadow mode.
MACD_HISTOGRAM_SIGNAL_ENABLED = False
# SELL მხარის ზღვარი, თუ მომავალში დაგვჭირდა
SELL_THRESHOLD = 10.0
# regime pass-ისთვის მინიმალური ADX
REGIME_ADX_MIN = 20.0
# ATR spike რამდენჯერ უნდა აჭარბებდეს ბაზას
ATR_SPIKE_MULTIPLIER = 1.10
# swing-ის საპოვნელად რამდენ candle-ს ვუყუროთ
SWING_LOOKBACK = 20
# ფასთან swing რამდენ %-ით ზემოთ უნდა იყოს
SWING_ABOVE_PCT = 0.005
# bounce-ის დასადასტურებლად რამდენ candle-ს ვუყუროთ
BOUNCE_LOOKBACK = 3
# resistance-ის საძებნი ფანჯარა
RESISTANCE_LOOKBACK = 30
# liquidity ზონის საძებნი ფანჯარა
LIQUIDITY_LOOKBACK = 30
# liquidity-ზე volume რამდენჯერ უნდა იყოს მეტი
LIQUIDITY_VOLUME_MULTIPLIER = 1.15
# liquidity tolerance რამდენ ATR-ზე დაითვალოს
LIQUIDITY_TOLERANCE_ATR_MULTIPLIER = 0.8

# პოზიციის აგების და რისკის პარამეტრები
SETUP_RR_RATIO = 2.0
SETUP_CONFIDENCE_MAX_SCORE = 18.0
ATR_STOP_MULTIPLIER = 1.5
FALLBACK_RISK_PCT = 1.5
EXIT_MONITORING_TIMEFRAME = "1m"

# Telegram bot alerts
TELEGRAM_BOT_ENABLED = os.getenv("TELEGRAM_BOT_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _parse_chat_ids(raw_value: str) -> frozenset[int]:
    values: set[int] = set()
    for raw_item in raw_value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            values.add(int(item))
        except ValueError:
            continue
    return frozenset(values)


# Optional allowlist; an empty value preserves the existing subscriber flow.
TELEGRAM_ALLOWED_CHAT_IDS = _parse_chat_ids(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", ""))

# permission/risk კონტროლი ახალი entry-სთვის
MIN_REQUIRED_BALANCE = 100.0
# V1 truth: exposure ceiling 900 ნიშნავს პრაქტიკულად დაახლოებით 9 x 100-იან პოზიციას
MAX_OPEN_EXPOSURE = 900.0
# count-based hard cap ამ ეტაპზე ძირითადი წესი აღარ არის; exposure არის მთავარი ceiling
MAX_OPEN_POSITIONS = 9
# თუ ახალი entry უკვე ახლოსაა მიმდინარე/ბოლო entry-სთან, დაიბლოკოს
DEFAULT_PROXIMITY_PCT = 0.5
# ახალი entry-ს შორის cooldown დრო წამებში
DEFAULT_COOLDOWN_SECONDS = 2 * 60 * 60
# თუ ღია პოზიცია -0.3% ან უარესად ზის, ახალი entry არ გაიხსნას
WEAK_OPEN_POSITION_PCT = -0.003
# research-backed BUY block: avoid stretched upper-extension entries.
BUY_ENTRY_BLOCKED_LOCATIONS = ("EXTENDED", "EXTENDED_INTO_RESISTANCE", "OVERHEATED_EXTENSION")

# orderbook ფილტრის მინიმალური/მაქსიმალური ზღვარები
ORDERBOOK_BUY_SELL_RATIO_MIN = 1.15
ORDERBOOK_SELL_BUY_RATIO_MIN = 1.15
ORDERBOOK_BULL_DOMINANCE_MIN = 0.25
ORDERBOOK_BEAR_DOMINANCE_MAX = -0.25
ORDERBOOK_BULL_IMBALANCE_MIN = 0.10
ORDERBOOK_BEAR_IMBALANCE_MAX = -0.10
ORDERBOOK_DIRECTIONAL_RATIO_NEUTRAL_MIN = 1.0
ORDERBOOK_DIRECTIONAL_RATIO_HEALTHY_MIN = 1.15
ORDERBOOK_DIRECTIONAL_RATIO_STRONG_MIN = 1.5
ORDERBOOK_DIRECTIONAL_RATIO_EXTREME_MIN = 2.0
ORDERBOOK_DIRECTIONAL_RATIO_BLOWOFF_MIN = 3.0
ORDERBOOK_DIRECTIONAL_DOMINANCE_HEALTHY_MIN = 0.10
ORDERBOOK_DIRECTIONAL_DOMINANCE_STRONG_MIN = 0.25
ORDERBOOK_DIRECTIONAL_DOMINANCE_EXTREME_MIN = 0.50
ORDERBOOK_DIRECTIONAL_IMBALANCE_CONFIRM_MIN = 0.05
ORDERBOOK_DIRECTIONAL_IMBALANCE_EXTREME_MIN = 0.50
STRUCTURE_LONG_LOW_DISTANCE_EARLY_ATR_MIN = 1.0
STRUCTURE_LONG_LOW_DISTANCE_HEALTHY_ATR_MIN = 1.5
STRUCTURE_LONG_LOW_DISTANCE_MID_ATR_MIN = 2.5
STRUCTURE_LONG_LOW_DISTANCE_EXTENSION_ATR_MIN = 4.0
STRUCTURE_LONG_LOW_DISTANCE_BLOWOFF_ATR_MIN = 6.0
STRUCTURE_LONG_SWING_HIGH_ROOM_MIN_ATR = 1.0
STRUCTURE_LONG_SWING_HIGH_ROOM_EXTENDED_ATR = 1.5

# weighted scoring-ში თითო კომპონენტის წონა
MTF_WEIGHT = 1.0
REGIME_WEIGHT = 0.8
TREND_WEIGHT = 1.3
MOMENTUM_WEIGHT = 1.0
ORDERBOOK_WEIGHT = 0.9
STRUCTURE_WEIGHT = 0.9

SIGNAL_COMPONENT_WEIGHTS = {
    "mtf": MTF_WEIGHT,
    "regime": REGIME_WEIGHT,
    "trend": TREND_WEIGHT,
    "momentum": MOMENTUM_WEIGHT,
    "orderbook": ORDERBOOK_WEIGHT,
    "structure": STRUCTURE_WEIGHT,
}

# raw component score-ის მინიმალური ზღვარები
MTF_RAW_GATE_MIN = 2.5
MTF_5M_TIMING_SCORE_MIN = 1.1
MTF_PRIMARY_SETUP_SCORE_MIN = 1.0
MTF_HIGHER_CONTEXT_SCORE_MIN = 0.8
REGIME_RAW_GATE_MIN = 1.0
TREND_RAW_MIN = 2.0
MOMENTUM_RAW_GATE_MIN = 2.0
ORDERBOOK_RAW_GATE_MIN = 1.5
STRUCTURE_RAW_GATE_MIN = 1.0

# Match Futures LONG account behavior; Spot remains unleveraged and BUY-only.
WEAK_OPEN_POSITION_BLOCK_ENABLED = False
PEER_FORCE_CLOSE_ENABLED = False
