from platform_v2.futures.config import settings
from platform_v2.shared.backend.market.structure_math import SnapshotFormat, StructureMathBase


class StructureMath(StructureMathBase):
    """Futures-configured shared structure and liquidity calculations."""

    BOUNCE_LOOKBACK = settings.BOUNCE_LOOKBACK
    LIQUIDITY_VOLUME_MULTIPLIER = settings.LIQUIDITY_VOLUME_MULTIPLIER
    LIQUIDITY_TOLERANCE_ATR_MULTIPLIER = settings.LIQUIDITY_TOLERANCE_ATR_MULTIPLIER
