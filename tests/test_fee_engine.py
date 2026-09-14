"""Engine-level tests: orchestration, discount, the out-of-hours boundary and the ports.

Every assertion here is possible only because the refactoring introduced injection.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from feeengine.adapters import StaticFxRateProvider
from feeengine.domain import FeeError, Tier, TransactionBuilder, TxType
from feeengine.engine import FeeEngine
from feeengine.rules import FeeRuleFactory


def at(hour, minute=0, second=0):
    """A fixed clock - the seam that makes the surcharge window testable."""
    moment = datetime(2026, 5, 12, hour, minute, second, tzinfo=timezone.utc)
    return lambda: moment


class FeeEngineTest(unittest.TestCase):

    def setUp(self):
        self.repository = MagicMock()
        self.audit = MagicMock()
        self.factory = FeeRuleFactory(StaticFxRateProvider())

    def engine_at(self, clock):
        return FeeEngine(self.factory, self.repository, self.audit, clock)

    def card(self, amount="100.00", tier=Tier.STANDARD):
        return TransactionBuilder().of_type(TxType.CARD).of_amount(amount).for_tier(tier).build()

    # ---- out-of-hours boundary (17:00 inclusive .. 08:00 exclusive) ----
    def test_out_of_hours_boundaries(self):
        cases = [
            (at(16, 59, 59), "1.20", "last second inside business hours"),
            (at(17, 0, 0), "1.45", "surcharge starts, inclusive"),
            (at(7, 59, 59), "1.45", "last second of the overnight window"),
            (at(8, 0, 0), "1.20", "window ends, exclusive"),
        ]
        for clock, expected, why in cases:
            with self.subTest(reason=why):
                self.assertEqual(Decimal(expected), self.engine_at(clock).price(self.card()).fee)

    # ---- tier discount ----
    def test_premium_halves_the_fee(self):
        result = self.engine_at(at(10)).price(self.card(tier=Tier.PREMIUM))
        self.assertEqual(Decimal("0.60"), result.fee)

    def test_standard_pays_full(self):
        self.assertEqual(Decimal("1.20"), self.engine_at(at(10)).price(self.card()).fee)

    # ---- validation ----
    def test_rejects_negative_amount(self):
        tx = TransactionBuilder().of_amount("-0.01").build()
        with self.assertRaises(FeeError):
            self.engine_at(at(10)).price(tx)

    def test_rejected_transaction_has_no_side_effects(self):
        tx = TransactionBuilder().of_type(TxType.CARD).in_currency("USD").build()
        with self.assertRaises(FeeError):
            self.engine_at(at(10)).price(tx)
        self.repository.save.assert_not_called()
        self.audit.record.assert_not_called()

    # ---- collaboration with the ports ----
    def test_persists_and_audits_once(self):
        result = self.engine_at(at(10)).price(self.card())
        self.repository.save.assert_called_once()
        self.audit.record.assert_called_once()
        self.assertEqual(Decimal("1.20"), self.repository.save.call_args[0][0].fee)
        self.assertIn("TX-1", self.audit.record.call_args[0][0])
        self.assertEqual(Decimal("1.20"), result.fee)

    # ---- strategy substitution ----
    def test_rule_can_be_substituted_without_touching_the_engine(self):
        promo = MagicMock()
        promo.base_fee.return_value = Decimal("9.99")
        promo.describe.return_value = "promo"
        self.factory.register(TxType.CARD, promo)
        self.assertEqual(Decimal("9.99"), self.engine_at(at(10)).price(self.card()).fee)

    # ---- FX through the engine ----
    def test_fx_priced_through_engine(self):
        tx = TransactionBuilder().of_type(TxType.FX).in_currency("USD").of_amount("100.00").build()
        self.assertEqual(Decimal("3.13"), self.engine_at(at(10)).price(tx).fee)


if __name__ == "__main__":
    unittest.main()
