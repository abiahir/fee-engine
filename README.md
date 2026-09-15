# FeeEngine — Module 7 (Software Testing and Design Patterns)

Transaction fee-pricing component: the subject system for the Module 7 analysis.
`feeengine/legacy.py` is the "before" baseline; the rest of the package is the "after".

Python, matching the module's taught toolchain (pytest, `unittest.mock`, coverage, GitHub Actions).

## Layout
```
feeengine/
  legacy.py      LegacyFeeProcessor + module-level CONFIG   <- the diagnosed baseline
  domain.py      Transaction (Builder), FeeResult, TxType, Tier, FeeError
  ports.py       FeeRepository, FxRateProvider, AuditLog    <- the injected seams
  rules.py       FeeRule (Strategy) + Card/Transfer/Fx + FeeRuleFactory
  engine.py      FeeEngine (injected collaborators + injected clock)
  adapters.py    in-memory repository, list audit log, static FX provider
tests/
  test_fee_rules.py                black-box partitions, boundaries, negative cases
  test_fee_engine.py               interaction verification with mock ports
  test_adapters_integration.py     state verification against the real adapters
  test_behavioural_equivalence.py  48-case legacy-vs-refactored regression harness
  test_legacy_characterisation.py  golden-master tests (skip outside business hours)
tools/
  coverage_report.py   stdlib statement coverage
  branch_coverage.py   stdlib decision (branch) coverage
  mutation_test.py     stdlib mutation analysis
```

## Patterns
| Category | Pattern | Where | Testability gained |
|---|---|---|---|
| Behavioural | **Strategy** | `rules.py` | each pricing rule is exercised in isolation |
| Structural | **Ports and adapters** | `ports.py` + `adapters.py` | collaborators become injectable, so tests attach doubles or real adapters as needed |
| Creational | **Builder** | `TransactionBuilder` | a test states only the field under test and inherits safe defaults |

The Builder was chosen over a keyword-default factory function because a fluent chain names each
varied field at the call site and gives a new field's default a single home — not because of any
threshold number of properties. The cost is six extra methods to maintain.

A simple **Factory** resolves the strategy. Deliberately **rejected**: Observer for audit (ADR-004,
one consumer, so dispatch machinery is unearned) and Abstract Factory (ADR-005, one product family).
Deliberately **deferred**: rules in configuration (ADR-006).

## Run
```bash
python3 -m unittest discover -s tests     # no third-party dependencies required
pytest                                    # same tests, module toolchain
pytest --cov=feeengine --cov-branch --cov-report=term-missing
python3 tools/coverage_report.py          # stdlib statement coverage
python3 tools/branch_coverage.py          # stdlib decision coverage
python3 tools/mutation_test.py            # stdlib mutation analysis
```

## Measured results
All figures below come from one run, retained verbatim in `06 Evidence/` of the project folder.
Run outside 08:00–17:00 UTC, so the three legacy characterisation tests report as skipped.

- **33 tests: 30 pass, 3 skip.** The skips are the legacy characterisation tests: they only run
  inside business hours because the legacy code reads `datetime.now()` internally.
- **Statement coverage:** refactored package 98.0%, legacy baseline 92.3%.
- **Decision coverage:** refactored package 100% (7 of 7 decisions, both outcomes taken);
  legacy 76.9% (10 of 13).
- **Mutation score:** 76.9% (13 mutants, 10 killed). The 3 survivors are provably equivalent —
  each turns a strict comparison into a non-strict one inside a clamp that assigns the boundary
  value, so at the only differing input the assignment writes the value already held.

The legacy module reaches 92.3% statement coverage only because the regression harness patches
`feeengine.legacy.datetime` to control the clock. That works, but the test then depends on the
production module's import statement; the injected clock in `engine.py` removes that coupling.
The legacy branch was never untestable — it was expensive to test durably.

Coverage is reported as a diagnostic, not a target.
