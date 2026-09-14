"""LEGACY baseline, kept verbatim as the 'before' state for the Module 7 diagnosis.

It works, and it is representative of a component extended repeatedly under delivery
pressure. It carries five testability defects that the report diagnoses:

1. God function - validation, rule selection, pricing, persistence and audit in one place.
2. if/elif chain on transaction type instead of polymorphism.
3. Collaborators created inside the function, so there is no seam for a test double.
4. datetime.now() read inline, so the out-of-hours branch is non-deterministic.
5. The discount rule written out three times.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from .domain import FeeError, Tier, Transaction, TxType

# Defect: module-level mutable global acting as a singleton config.
CONFIG = {
    "card.rate": "0.012", "card.cap": "5.00", "card.min": "0.20",
    "transfer.low": "0.50", "transfer.high": "1.50",
    "fx.rate": "0.025", "fx.min": "1.00",
    "outOfHours.surcharge": "0.25",
}


class LegacyFeeProcessor:
    def __init__(self) -> None:
        # Defect 3: hard-wired collaborators, no interface, no injection point.
        self.database: list[str] = []
        self.audit_trail: list[str] = []

    def process(self, tx: Transaction) -> Decimal:
        # Defect 1: validation fused to pricing.
        if tx is None:
            raise FeeError("transaction required")
        if tx.amount < 0:
            raise FeeError("amount must be >= 0")
        if tx.currency != "GBP" and tx.type is not TxType.FX:
            raise FeeError("non-GBP only supported for FX")

        # Defect 2: type dispatch by if/elif.
        if tx.type is TxType.CARD:
            fee = tx.amount * Decimal(CONFIG["card.rate"])
            if fee > Decimal(CONFIG["card.cap"]):
                fee = Decimal(CONFIG["card.cap"])
            if fee < Decimal(CONFIG["card.min"]):
                fee = Decimal(CONFIG["card.min"])
            # Defect 5: discount, occurrence 1 of 3.
            if tx.tier is Tier.PREMIUM:
                fee = (fee * Decimal("0.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif tx.type is TxType.TRANSFER:
            fee = (Decimal(CONFIG["transfer.high"]) if tx.amount >= Decimal("1000.00")
                   else Decimal(CONFIG["transfer.low"]))
            # Defect 5: occurrence 2 of 3.
            if tx.tier is Tier.PREMIUM:
                fee = (fee * Decimal("0.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif tx.type is TxType.FX:
            rate = Decimal("1.25")  # hard-coded; no seam for a live lookup
            fee = (tx.amount * rate) * Decimal(CONFIG["fx.rate"])
            if fee < Decimal(CONFIG["fx.min"]):
                fee = Decimal(CONFIG["fx.min"])
            # Defect 5: occurrence 3 of 3.
            if tx.tier is Tier.PREMIUM:
                fee = (fee * Decimal("0.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            raise FeeError(f"unsupported type {tx.type}")

        # Defect 4: ambient clock - this branch cannot be driven deterministically.
        hour = datetime.now(timezone.utc).hour
        if hour >= 17 or hour < 8:
            fee = fee + Decimal(CONFIG["outOfHours.surcharge"])

        fee = fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Defect 1 again: persistence and audit inseparable from calculation.
        self.database.append(f"{tx.id}={fee}")
        self.audit_trail.append(f"priced {tx.id} at {datetime.now(timezone.utc)}")
        return fee
