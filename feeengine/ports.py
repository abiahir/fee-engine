"""Outbound ports. These interfaces are the seams that make the engine testable."""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .domain import FeeResult


class FeeRepository(Protocol):
    def save(self, result: FeeResult) -> None: ...


class FxRateProvider(Protocol):
    def rate_for(self, currency: str) -> Decimal: ...


class AuditLog(Protocol):
    def record(self, message: str) -> None: ...
