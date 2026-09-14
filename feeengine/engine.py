"""Fee engine: orchestration only."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from .domain import FeeError, FeeResult, Tier, Transaction, TxType
from .ports import AuditLog, FeeRepository
from .rules import FeeRuleFactory

PREMIUM_DISCOUNT = Decimal("0.5")
OUT_OF_HOURS_FROM = 17   # inclusive
OUT_OF_HOURS_UNTIL = 8   # exclusive


def _system_clock() -> datetime:
    return datetime.now(timezone.utc)


class FeeEngine:
    """Prices a transaction and records the outcome.

    Every collaborator - rules, repository, audit sink and the clock - is injected, so a
    test supplies exactly the doubles it needs. The tier discount, which the legacy version
    repeated in three branches, is defined once here.
    """

    def __init__(
        self,
        rules: FeeRuleFactory,
        repository: FeeRepository,
        audit: AuditLog,
        clock: Callable[[], datetime] = _system_clock,
        out_of_hours_surcharge: Decimal = Decimal("0.25"),
    ) -> None:
        self._rules = rules
        self._repository = repository
        self._audit = audit
        self._clock = clock
        self._surcharge = out_of_hours_surcharge

    def price(self, tx: Transaction) -> FeeResult:
        self._validate(tx)

        rule = self._rules.rule_for(tx.type)
        fee = rule.base_fee(tx)
        fee = self._apply_tier_discount(fee, tx.tier)
        fee = self._apply_out_of_hours(fee)

        result = FeeResult(
            transaction_id=tx.id,
            fee=fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            explanation=rule.describe(),
        )
        self._repository.save(result)
        self._audit.record(f"priced {tx.id} fee={result.fee}")
        return result

    @staticmethod
    def _validate(tx: Transaction) -> None:
        if tx is None:
            raise FeeError("transaction required")
        if tx.amount < 0:
            raise FeeError("amount must be >= 0")
        if tx.currency != "GBP" and tx.type is not TxType.FX:
            raise FeeError("non-GBP only supported for FX")

    @staticmethod
    def _apply_tier_discount(fee: Decimal, tier: Tier) -> Decimal:
        if tier is Tier.PREMIUM:
            return (fee * PREMIUM_DISCOUNT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return fee

    def _apply_out_of_hours(self, fee: Decimal) -> Decimal:
        hour = self._clock().astimezone(timezone.utc).hour
        if hour >= OUT_OF_HOURS_FROM or hour < OUT_OF_HOURS_UNTIL:
            return fee + self._surcharge
        return fee
