"""Shared source boundary for research tests, independent of test subfolder depth."""
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parents[3]
