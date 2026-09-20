"""Domain-neutral backend helpers shared by Spot, Futures, Hedge, and tools."""

from .serialization import to_runtime_dict
from .time import utc_now_ms

__all__ = ["to_runtime_dict", "utc_now_ms"]
