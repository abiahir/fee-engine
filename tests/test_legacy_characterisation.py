"""Characterisation ('golden master') tests written BEFORE refactoring.

Their purpose is not to assert the legacy behaviour is correct, but to pin what it does so
the refactoring can be shown to preserve it (Feathers, 2004).

They also demonstrate the defect: because the legacy processor reads the clock internally,
these tests must be skipped outside business hours. A test that can only run for part of
the day is itself evidence of the design problem being fixed.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from feeengine.domain import Tier, TransactionBuilder, TxType
from feeengine.legacy import LegacyFeeProcessor


def within_business_hours():
    return 8 <= datetime.now(timezone.utc).hour < 17


SKIP_REASON = ("legacy reads datetime.now() internally, so the expected value changes with "
               "the time of day - this is the untestability being fixed")


class LegacyCharacterisationTest(unittest.TestCase):

    def setUp(self):
        self.legacy = LegacyFeeProcessor()

    @unittest.skipUnless(within_business_hours(), SKIP_REASON)
    def test_pins_card_pricing(self):
        tx = TransactionBuilder().of_type(TxType.CARD).of_amount("100.00").build()
        self.assertEqual(Decimal("1.20"), self.legacy.process(tx))

    @unittest.skipUnless(within_business_hours(), SKIP_REASON)
    def test_pins_transfer_threshold(self):
        below = TransactionBuilder().of_type(TxType.TRANSFER).of_amount("999.99").build()
        at_threshold = TransactionBuilder().of_type(TxType.TRANSFER).of_amount("1000.00").build()
        self.assertEqual(Decimal("0.50"), self.legacy.process(below))
        self.assertEqual(Decimal("1.50"), self.legacy.process(at_threshold))

    @unittest.skipUnless(within_business_hours(), SKIP_REASON)
    def test_pins_premium_discount(self):
        tx = (TransactionBuilder().of_type(TxType.CARD).of_amount("100.00")
              .for_tier(Tier.PREMIUM).build())
        self.assertEqual(Decimal("0.60"), self.legacy.process(tx))


if __name__ == "__main__":
    unittest.main()
