"""Canonical independent Spot decision service. Historical rules live in research."""

from .independent_long_signal_service import IndependentLongSignalService

SignalDecisionService = IndependentLongSignalService
