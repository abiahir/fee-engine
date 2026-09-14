"""Fee rules.

Strategy (behavioural): one rule per product, each independently testable.
Factory (creational): resolves the rule for a transaction type.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .domain import FeeError, Transaction, TxType
from .ports import FxRateProvider


class FeeRule(Protocol):
    def base_fee(self, tx: Transaction) -> Decimal: ...
    def describe(self) -> str: ...


class CardFeeRule:
    """Percentage of value, floored at a minimum and capped at a maximum."""

    def __init__(self, rate: Decimal, minimum: Decimal, cap: Decimal) -> None:
        self._rate, self._min, self._cap = rate, minimum, cap

    @staticmethod
    def standard() -> "CardFeeRule":
        return CardFeeRule(Decimal("0.012"), Decimal("0.20"), Decimal("5.00"))

    def base_fee(self, tx: Transaction) -> Decimal:
        fee = tx.amount * self._rate
        if fee > self._cap:
            fee = self._cap
        if fee < self._min:
            fee = self._min
        return fee

    def describe(self) -> str:
        return f"card {self._rate} min {self._min} cap {self._cap}"


class TransferFeeRule:
    """Flat fee that steps up at or above a value threshold."""

    def __init__(self, threshold: Decimal, low: Decimal, high: Decimal) -> None:
        self._threshold, self._low, self._high = threshold, low, high

    @staticmethod
    def standard() -> "TransferFeeRule":
        return TransferFeeRule(Decimal("1000.00"), Decimal("0.50"), Decimal("1.50"))

    def base_fee(self, tx: Transaction) -> Decimal:
        return self._high if tx.amount >= self._threshold else self._low

    def describe(self) -> str:
        return f"transfer step at {self._threshold}"


class FxFeeRule:
    """Converts with an injected rate provider, then charges a percentage with a floor."""

    def __init__(self, rates: FxRateProvider, rate: Decimal, minimum: Decimal) -> None:
        self._rates, self._rate, self._min = rates, rate, minimum

    @staticmethod
    def standard(rates: FxRateProvider) -> "FxFeeRule":
        return FxFeeRule(rates, Decimal("0.025"), Decimal("1.00"))

    def base_fee(self, tx: Transaction) -> Decimal:
        converted = tx.amount * self._rates.rate_for(tx.currency)
        fee = converted * self._rate
        return self._min if fee < self._min else fee

    def describe(self) -> str:
        return f"fx {self._rate} min {self._min}"


class FeeRuleFactory:
    """Factory. A plain mapping is deliberate - see ADR-005 (Abstract Factory rejected)."""

    def __init__(self, rates: FxRateProvider) -> None:
        self._rules: dict[TxType, FeeRule] = {
            TxType.CARD: CardFeeRule.standard(),
            TxType.TRANSFER: TransferFeeRule.standard(),
            TxType.FX: FxFeeRule.standard(rates),
        }

    def register(self, tx_type: TxType, rule: FeeRule) -> "FeeRuleFactory":
        self._rules[tx_type] = rule
        return self

    def rule_for(self, tx_type: TxType) -> FeeRule:
        try:
            return self._rules[tx_type]
        except KeyError:
            raise FeeError(f"no rule registered for {tx_type}") from None
