# FeeEngine — Module 7 (Software Testing and Design Patterns)

Transaction fee-pricing component: the subject system for the Module 7 analysis.
`feeengine/legacy.py` is the "before" baseline; the rest of the package is the "after".

Python, matching the module's taught toolchain (pytest, `unittest.mock`, coverage, GitHub Actions).

## Layout
```
feeengine/
  legacy.py      LegacyFeeProcessor + global CONFIG    <- the diagnosed baseline
  domain.py      Transaction (Builder), FeeResult, TxType, Tier, FeeError
  ports.py       FeeRepository, FxRateProvider, AuditLog   <- the injected seams
  rules.py       FeeRule (Strategy) + Card/Transfer/Fx + FeeRuleFactory
  engine.py      FeeEngine (injected collaborators + injected clock)
  adapters.py    in-memory repository, list audit log, static FX provider
tests/           unittest + unittest.mock (pytest runs these natively)
tools/           coverage_report.py - stdlib-only coverage measurement
```

## One pattern per category (the module's scoping rule)
| Category | Pattern | Where | Testability gained |
|---|---|---|---|
| Creational | **Builder** | `TransactionBuilder` | 6 construction properties ⇒ Builder over Factory (module heuristic: ≥5 ⇒ Builder); tests state only the field under test |
| Structural | **Adapter / Ports** | `ports.py` + `adapters.py` | dependencies become injectable, so `MagicMock` doubles replace infrastructure |
| Behavioural | **Strategy** | `rules.py` | each pricing rule is exercised in isolation |

Supporting: a simple **Factory** resolves the strategy. Deliberately **rejected**: Observer/event bus
for audit (ADR-004) and Abstract Factory (ADR-005) — see the ADR.

## Run
```bash
python3 -m unittest discover -s tests -t .    # no dependencies required
pytest                                        # same tests, module toolchain
pytest --cov=feeengine --cov-report=term-missing
python3 tools/coverage_report.py              # stdlib-only measured coverage
```

## Measured results (real runs, this repository)
- **16 tests pass, 3 skipped.** The 3 skips are the legacy characterisation tests: they can
  only run inside business hours because the legacy code reads `datetime.now()` internally.
- **Refactored package: 91.2% statement coverage** (135/148).
- **Legacy baseline: 10.3%** (4/39) — its only tests were skipped at the time of measurement.

Coverage is reported as a diagnostic, not a target: the module's own guidance is that high-quality
test cases matter more than a coverage percentage.
