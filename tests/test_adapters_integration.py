"""Integration tests: the engine wired to real adapters, not mocks.

The engine tests in ``test_fee_engine.py`` use mocks to verify *interaction* - that save and
record are called once, with the right argument. These tests verify *state*: that the real
in-memory adapters actually hold what the engine put there. Meszaros (2007) separates those
two styles for a reason, and a suite that only ever mocks the outbound ports never exercises
the adapters it ships with.

They also cover the failure contract at the boundary: what is persisted and audited when
pricing is rejected, and what happens when a rate is unavailable.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from feeengine.adapters import InMemoryFeeRepository, ListAuditLog, StaticFxRateProvider
from feeengine.domain import FeeError, Tier, TransactionBuilder, TxType
from feeengine.engine import FeeEngine
from feeengine.rules import FeeRuleFactory

AT_1000 = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)


class AdapterIntegrationTest(unittest.TestCase):

    def setUp(self):
        self.repository = InMemoryFeeRepository()
        self.audit = ListAuditLog()
        self.engine = FeeEngine(
            FeeRuleFactory(StaticFxRateProvider()),
            self.repository,
            self.audit,
            lambda: AT_1000,
        )

    def test_priced_transaction_is_stored_in_the_repository(self):
        result = self.engine.price(
            TransactionBuilder().of_type(TxType.CARD).of_amount("100.00").build())

        self.assertEqual(1, len(self.repository.saved))
        stored = self.repository.saved[0]
        self.assertEqual("TX-1", stored.transaction_id)
        self.assertEqual(Decimal("1.20"), stored.fee)
        self.assertEqual(result, stored)

    def test_audit_entry_names_the_transaction_and_the_fee(self):
        self.engine.price(
            TransactionBuilder().of_type(TxType.CARD).of_amount("100.00").build())

        self.assertEqual(1, len(self.audit.entries))
        self.assertIn("TX-1", self.audit.entries[0])
        self.assertIn("1.20", self.audit.entries[0])

    def test_each_transaction_adds_one_record_to_each_adapter(self):
        for i in range(3):
            self.engine.price(
                TransactionBuilder().with_id(f"TX-{i}").of_amount("100.00").build())

        self.assertEqual(3, len(self.repository.saved))
        self.assertEqual(3, len(self.audit.entries))
        self.assertEqual(["TX-0", "TX-1", "TX-2"],
                         [r.transaction_id for r in self.repository.saved])

    def test_explanation_records_which_rule_priced_it(self):
        """The stored result carries the rule's own description, so an audit can trace it."""
        result = self.engine.price(
            TransactionBuilder().of_type(TxType.TRANSFER).of_amount("2000.00").build())
        self.assertIn("transfer", result.explanation)
        self.assertEqual(result.explanation, self.repository.saved[0].explanation)


class BoundaryFailureTest(unittest.TestCase):
    """Negative cases at the engine boundary, against real adapters."""

    def setUp(self):
        self.repository = InMemoryFeeRepository()
        self.audit = ListAuditLog()
        self.engine = FeeEngine(
            FeeRuleFactory(StaticFxRateProvider()),
            self.repository,
            self.audit,
            lambda: AT_1000,
        )

    def assertNothingRecorded(self):
        self.assertEqual([], self.repository.saved)
        self.assertEqual([], self.audit.entries)

    def test_missing_transaction_is_rejected_and_records_nothing(self):
        with self.assertRaises(FeeError):
            self.engine.price(None)
        self.assertNothingRecorded()

    def test_negative_amount_is_rejected_and_records_nothing(self):
        with self.assertRaises(FeeError):
            self.engine.price(TransactionBuilder().of_amount("-0.01").build())
        self.assertNothingRecorded()

    def test_unsupported_currency_for_a_non_fx_product_records_nothing(self):
        with self.assertRaises(FeeError):
            self.engine.price(
                TransactionBuilder().of_type(TxType.CARD).in_currency("USD").build())
        self.assertNothingRecorded()

    def test_unknown_fx_currency_fails_before_anything_is_written(self):
        """A rate lookup failure must not leave a half-completed record behind.

        This is the case that motivates the ordering in FeeEngine.price: pricing is
        completed before either outbound port is touched.
        """
        tx = (TransactionBuilder().of_type(TxType.FX).in_currency("JPY")
              .of_amount("100.00").build())
        with self.assertRaises(FeeError):
            self.engine.price(tx)
        self.assertNothingRecorded()


if __name__ == "__main__":
    unittest.main()
