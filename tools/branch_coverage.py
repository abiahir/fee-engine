"""Decision (branch) coverage for the feeengine package, using only the standard library.

Statement coverage and branch coverage are not the same measurement. A statement-coverage
tool reports a conditional as covered as soon as the line executes, whichever way it went;
it therefore cannot tell you that the false arm of a guard was never taken. Because
coverage.py is not installed in the marking environment, this tool measures decisions
directly.

Method
------
1.  ``sys.settrace`` records, per frame, the arcs (from_line -> to_line) actually taken. A
    ``return`` event records the synthetic arc (from_line -> -1), so a conditional whose
    false arm exits the function is not miscounted as unexercised.
2.  ``ast`` locates every ``if``, ``while`` and ``assert`` and the first line of its true arm.
3.  A decision is covered when the arc into its true arm was taken *and* at least one other
    arc out of the decision line was taken.

Scope and limits, stated plainly
--------------------------------
*   This is decision coverage, not condition or MC/DC coverage: ``a and b`` is one decision,
    so a short-circuit that never evaluates ``b`` is not detected.
*   ``try``/``except`` arms and comprehension filters are not treated as decisions.
*   The package is removed from ``sys.modules`` before tracing starts, so module-level code
    is measured too.

Run from the repository root:  python tools/branch_coverage.py
"""
from __future__ import annotations

import ast
import io
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "feeengine"
EXIT = -1


def decisions(path: Path) -> tuple[dict[int, int], int]:
    """Map each decision line to the first line of its true arm.

    Returns the map plus a count of conditional *expressions* (``x if c else y``). Those are
    decisions too, but when written on one line they produce no distinguishable line arc, so
    this tool reports them separately rather than scoring them.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[int, int] = {}
    ternaries = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)) and node.body:
            found[node.test.lineno] = node.body[0].lineno
        elif isinstance(node, ast.Assert):
            found[node.lineno] = node.lineno
        elif isinstance(node, ast.IfExp):
            ternaries += 1
    return found, ternaries


def make_tracer(watched: set[str], arcs: dict[str, set[tuple[int, int]]]):
    """A settrace callback that records line-to-line arcs for the watched files."""
    previous: dict[int, int] = {}

    def local(frame, event, arg):
        name = frame.f_code.co_filename
        key = id(frame)
        if event == "line":
            if key in previous:
                arcs[name].add((previous[key], frame.f_lineno))
            previous[key] = frame.f_lineno
        elif event == "return" and key in previous:
            arcs[name].add((previous.pop(key), EXIT))
        return local

    def tracer(frame, event, arg):
        return local if frame.f_code.co_filename in watched else None

    return tracer


def run_suite() -> None:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    for module in [m for m in sys.modules if m.startswith("feeengine")]:
        del sys.modules[module]

    sources = sorted(p for p in PACKAGE.glob("*.py") if p.name != "__init__.py")
    arcs: dict[str, set[tuple[int, int]]] = defaultdict(set)

    sys.settrace(make_tracer({str(p) for p in sources}, arcs))
    try:
        run_suite()
    finally:
        sys.settrace(None)

    print(f"{'module':<16}{'decisions':>10}{'covered':>9}{'%':>8}   partly covered")
    print("-" * 74)
    total = hit_total = ternary_total = 0
    for source in sources:
        found, ternaries = decisions(source)
        ternary_total += ternaries
        taken = arcs.get(str(source), set())
        partial = []
        for line, true_arm in sorted(found.items()):
            outgoing = {to for frm, to in taken if frm == line}
            took_true = true_arm in outgoing
            took_false = bool(outgoing - {true_arm})
            if took_true and took_false:
                hit_total += 1
            else:
                which = "true only" if took_true else "false only" if took_false else "never run"
                partial.append(f"line {line} ({which})")
        count = len(found)
        hit = count - len(partial)
        total += count
        pct = (hit / count * 100) if count else 100.0
        note = '; '.join(partial) or '-'
        if ternaries:
            note += f"  [+{ternaries} conditional expr, not line-traceable]"
        print(f"{source.name:<16}{count:>10}{hit:>9}{pct:>7.1f}%   {note}")

    print("-" * 74)
    overall = (hit_total / total * 100) if total else 100.0
    print(f"{'TOTAL':<16}{total:>10}{hit_total:>9}{overall:>7.1f}%")
    print(f"Conditional expressions not scored by this tool: {ternary_total}")
    print("\nDecision coverage only: 'a and b' counts as one decision, so short-circuit")
    print("evaluation of the right-hand operand is not measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
