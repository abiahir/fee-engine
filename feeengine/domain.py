"""Domain types for fee pricing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class TxType(Enum):
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    FX = "FX"


class Tier(Enum):
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class FeeError(Exception):
    """Raised when a transaction cannot be priced."""


@dataclass(frozen=True)
class Transaction:
    """An immutable transaction presented for pricing.

    Six construction properties (id, type, amount, currency, tier, occurred_at).
    The module's creational heuristic is that a Factory is sufficient below about five
    properties, and a Builder is preferable at five or more - which is why construction
    goes through TransactionBuilder rather than a factory function.
    """

    id: str
    type: TxType
    amount: Decimal
    currency: str
    tier: Tier
    occurred_at: datetime


class TransactionBuilder:
    """Builder. Defaults let a test state only the field under test."""

    def __init__(self) -> None:
        self._id = "TX-1"
        self._type = TxType.CARD
        self._amount = Decimal("10.00")
        self._currency = "GBP"
        self._tier = Tier.STANDARD
        self._occurred_at = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)

    def with_id(self, value: str) -> "TransactionBuilder":
        self._id = value
        return self

    def of_type(self, value: TxType) -> "TransactionBuilder":
        self._type = value
        return self

    def of_amount(self, value: str | Decimal) -> "TransactionBuilder":
        self._amount = Decimal(value)
        return self

    def in_currency(self, value: str) -> "TransactionBuilder":
        self._currency = value
        return self

    def for_tier(self, value: Tier) -> "TransactionBuilder":
        self._tier = value
        return self

    def occurring_at(self, value: datetime) -> "TransactionBuilder":
        self._occurred_at = value
        return self

    def build(self) -> Transaction:
        return Transaction(
            id=self._id,
            type=self._type,
            amount=self._amount,
            currency=self._currency,
            tier=self._tier,
            occurred_at=self._occurred_at,
        )


@dataclass(frozen=True)
class FeeResult:
    transaction_id: str
    fee: Decimal
    explanation: str
