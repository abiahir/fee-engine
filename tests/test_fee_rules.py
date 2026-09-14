"""Black-box tests for the individual fee rules (Strategy implementations).

Techniques: equivalence partitioning and boundary value analysis. Each rule is exercised
on its own - which the legacy if/elif chain made impossible.
"""
import unittest
from decimal import ROUND_HALF_UP, Decimal

from feeengine.domain import TransactionBuilder, TxType
from feeengine.rules import CardFeeRule, TransferFeeRule, FxFeeRule


def card(amount):
    return TransactionBuilder().of_type(TxType.CARD).of_amount(amount).build()


def p(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CardFeeRuleTest(unittest.TestCase):
    """Three equivalence classes: below floor, proportional band, above cap."""

    def setUp(self):
        self.rule = CardFeeRule.standard()  # 1.2%, floor 0.20, cap 5.00

    def test_partitions_and_boundaries(self):
        cases = [
            ("0.00", "0.20", "floor: zero value still attracts the minimum"),
            ("16.66", "0.20", "floor boundary: 1.2% = 0.19992, just below the floor"),
            ("16.67", "0.20", "floor boundary: 1.2% = 0.20004, just above the floor"),
            ("100.00", "1.20", "proportional band"),
            ("416.66", "5.00", "cap boundary: 1.2% = 4.99992, just under the cap"),
            ("416.67", "5.00", "cap boundary: 1.2% = 5.00004, capped"),
            ("10000.00", "5.00", "well above the cap"),
        ]
        for amount, expected, partition in cases:
            with self.subTest(amount=amount, partition=partition):
                self.assertEqual(Decimal(expected), p(self.rule.base_fee(card(amount))))

    def test_rule_is_configurable_without_code_change(self):
        promo = CardFeeRule(Decimal("0.005"), Decimal("0.10"), Decimal("2.00"))
        self.assertEqual(Decimal("0.50"), p(promo.base_fee(card("100.00"))))


class TransferFeeRuleTest(unittest.TestCase):
    """Boundary value analysis: the step is inclusive at the threshold."""

    def setUp(self):
        self.rule = TransferFeeRule.standard()

    def test_threshold_is_inclusive(self):
        cases = [
            ("0.00", "0.50"), ("999.98", "0.50"), ("999.99", "0.50"),
            ("1000.00", "1.50"),   # on the boundary - inclusive
            ("1000.01", "1.50"), ("50000.00", "1.50"),
        ]
        for amount, expected in cases:
            with self.subTest(amount=amount):
                tx = TransactionBuilder().of_type(TxType.TRANSFER).of_amount(amount).build()
                self.assertEqual(Decimal(expected), self.rule.base_fee(tx))


class FxFeeRuleTest(unittest.TestCase):
    """The rate provider is mocked, so the arithmetic is deterministic.

    In the legacy version the rate was a literal inside the function, so this branch could
    not be priced under test at all.
    """

    def test_converts_then_charges_percentage(self):
        from unittest.mock import MagicMock

        rates = MagicMock()
        rates.rate_for.return_value = Decimal("1.25")
        rule = FxFeeRule.standard(rates)

        tx = TransactionBuilder().of_type(TxType.FX).in_currency("USD").of_amount("100.00").build()
        # 100 USD x 1.25 = 125.00 ; 2.5% = 3.125 -> 3.13 at 2dp
        self.assertEqual(Decimal("3.13"), p(rule.base_fee(tx)))
        rates.rate_for.assert_called_once_with("USD")

    def test_applies_minimum(self):
        from unittest.mock import MagicMock

        rates = MagicMock()
        rates.rate_for.return_value = Decimal("1.15")
        rule = FxFeeRule.standard(rates)
        tx = TransactionBuilder().of_type(TxType.FX).in_currency("EUR").of_amount("1.00").build()
        self.assertEqual(Decimal("1.00"), rule.base_fee(tx))


if __name__ == "__main__":
    unittest.main()
