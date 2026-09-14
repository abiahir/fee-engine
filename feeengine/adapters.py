"""Adapters implementing the outbound ports."""
from __future__ import annotations

from decimal import Decimal

from .domain import FeeError, FeeResult


class InMemoryFeeRepository:
    def __init__(self) -> None:
        self.saved: list[FeeResult] = []

    def save(self, result: FeeResult) -> None:
        self.saved.append(result)


class ListAuditLog:
    def __init__(self) -> None:
        self.entries: list[str] = []

    def record(self, message: str) -> None:
        self.entries.append(message)


class StaticFxRateProvider:
    """Fixed-table stand-in for the live rates service."""

    _RATES = {"GBP": Decimal("1"), "USD": Decimal("1.25"), "EUR": Decimal("1.15")}

    def rate_for(self, currency: str) -> Decimal:
        try:
            return self._RATES[currency]
        except KeyError:
            raise FeeError(f"no FX rate for {currency}") from None
