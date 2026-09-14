"""Deterministic legacy-vs-refactored regression comparison.

This is the acceptance test for the refactoring. It answers the question a stakeholder asks
first: did the restructuring change what a customer is charged?

Two things make the comparison deterministic, and both are deliberate:

1.  The legacy clock is controlled by replacing the ``datetime`` symbol in the legacy
    module's own namespace. That works, but it is a test that knows the production module's
    import statement - the coupling ADR-002 removes. The refactored engine needs no such
    trick; it is given a clock.
2.  The legacy processor hard-codes a single FX rate of 1.25 for every currency. To compare
    structure rather than rates, the refactored engine is given a rate provider that
    reproduces that constant (``LegacyRateProvider``). The production rate table is a
    separate, intentional business change and is pinned separately in
    ``ApprovedBehaviourChangeTest`` below - recorded, not hidden.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from feeengine.adapters import InMemoryFeeRepository, ListAuditLog, StaticFxRateProvider
from feeengine.domain import Tier, TransactionBuilder, TxType
from feeengine.engine import FeeEngine
from feeengine.legacy import LegacyFeeProcessor
from feeengine.rules import FeeRuleFactory

LEGACY_FX_RATE = Decimal("1.25")


class LegacyRateProvider:
    """Reproduces the legacy constant rate so the comparison isolates structure from rates."""

    def rate_for(self, currency: str) -> Decimal:
        return LEGACY_FX_RATE


def moment(hour, minute=0, second=0):
    return datetime(2026, 5, 12, hour, minute, second, tzinfo=timezone.utc)


def frozen_datetime(at):
    """A stand-in for the datetime class the legacy module imported."""

    class _Frozen:
        @staticmethod
        def now(tz=None):
            return at

    return _Frozen


# Product x tier x monetary boundary. Currencies are legal for the product under test.
CASES = [
    (TxType.CARD, "0.00", "GBP", Tier.STANDARD, "card floor, zero amount"),
    (TxType.CARD, "16.66", "GBP", Tier.STANDARD, "card just below the floor crossover"),
    (TxType.CARD, "16.67", "GBP", Tier.STANDARD, "card at the floor crossover"),
    (TxType.CARD, "416.67", "GBP", Tier.STANDARD, "card at the cap crossover"),
    (TxType.CARD, "1000.00", "GBP", Tier.STANDARD, "card well above the cap"),
    (TxType.CARD, "100.00", "GBP", Tier.PREMIUM, "card, premium discount"),
    (TxType.TRANSFER, "999.99", "GBP", Tier.STANDARD, "transfer below the threshold"),
    (TxType.TRANSFER, "1000.00", "GBP", Tier.STANDARD, "transfer at the threshold"),
    (TxType.TRANSFER, "1000.00", "GBP", Tier.PREMIUM, "transfer at threshold, premium"),
    (TxType.FX, "10.00", "USD", Tier.STANDARD, "fx below the minimum fee"),
    (TxType.FX, "100.00", "USD", Tier.STANDARD, "fx above the minimum fee"),
    (TxType.FX, "100.00", "USD", Tier.PREMIUM, "fx, premium discount"),
]

# The four clock boundaries of the out-of-hours window.
HOURS = [moment(16, 59, 59), moment(17, 0, 0), moment(7, 59, 59), moment(8, 0, 0)]


class BehaviouralEquivalenceTest(unittest.TestCase):
    """48 comparisons: 12 pricing cases at each of 4 clock boundaries."""

    def refactored(self, at):
        return FeeEngine(
            FeeRuleFactory(LegacyRateProvider()),
            InMemoryFeeRepository(),
            ListAuditLog(),
            lambda: at,
        )

    def test_refactored_matches_legacy_on_every_case(self):
        for tx_type, amount, currency, tier, why in CASES:
            for at in HOURS:
                with self.subTest(case=why, at=at.strftime("%H:%M:%S")):
                    tx = (TransactionBuilder().of_type(tx_type).of_amount(amount)
                          .in_currency(currency).for_tier(tier).build())
                    with patch("feeengine.legacy.datetime", frozen_datetime(at)):
                        expected = LegacyFeeProcessor().process(tx)
                    self.assertEqual(expected, self.refactored(at).price(tx).fee)

    def test_both_implementations_reject_the_same_invalid_input(self):
        """Equivalence covers the error contract, not only the happy path."""
        from feeengine.domain import FeeError

        tx = TransactionBuilder().of_type(TxType.CARD).in_currency("USD").build()
        with patch("feeengine.legacy.datetime", frozen_datetime(moment(10))):
            with self.assertRaises(FeeError):
                LegacyFeeProcessor().process(tx)
        with self.assertRaises(FeeError):
            self.refactored(moment(10)).price(tx)


class ApprovedBehaviourChangeTest(unittest.TestCase):
    """The one place the refactored engine is *meant* to differ from the legacy baseline.

    The legacy processor charges every FX transaction as though the rate were 1.25,
    whatever the currency. The refactored engine converts at a per-currency rate. That is a
    business-rule correction, not a refactoring, so it is pinned here with its expected
    values rather than being allowed to hide inside the equivalence suite.
    """

    def engine(self):
        return FeeEngine(
            FeeRuleFactory(StaticFxRateProvider()),
            InMemoryFeeRepository(),
            ListAuditLog(),
            lambda: moment(10),
        )

    def test_per_currency_rates_replace_the_single_hard_coded_rate(self):
        expected = {"USD": "3.13", "EUR": "2.88", "GBP": "2.50"}
        for currency, fee in expected.items():
            with self.subTest(currency=currency):
                tx = (TransactionBuilder().of_type(TxType.FX).of_amount("100.00")
                      .in_currency(currency).build())
                self.assertEqual(Decimal(fee), self.engine().price(tx).fee)

    def test_only_usd_is_unchanged_from_the_legacy_baseline(self):
        """USD matches because the legacy constant happened to be the USD rate."""
        for currency, same in (("USD", True), ("EUR", False), ("GBP", False)):
            with self.subTest(currency=currency):
                tx = (TransactionBuilder().of_type(TxType.FX).of_amount("100.00")
                      .in_currency(currency).build())
                with patch("feeengine.legacy.datetime", frozen_datetime(moment(10))):
                    legacy = LegacyFeeProcessor().process(tx)
                self.assertEqual(same, legacy == self.engine().price(tx).fee)


if __name__ == "__main__":
    unittest.main()
