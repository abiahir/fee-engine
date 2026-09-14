"""Line-coverage report using only the standard library (trace).

Used to produce measured coverage in an environment where coverage.py cannot be installed.
CI uses pytest + coverage.py; this produces the same statement-coverage measure locally so
the report can quote a real number rather than an estimate.

Usage:  python3 tools/coverage_report.py
"""
import sys, trace, unittest, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TARGETS = ["engine.py", "rules.py", "domain.py", "adapters.py", "legacy.py"]


def executable_lines(path):
    """Statements we expect to execute: excludes blanks, comments, docstrings, imports-only."""
    import ast
    src = path.read_text()
    tree = ast.parse(src)
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(node, (ast.Import, ast.ImportFrom)):
            # skip module/class/function docstring expressions
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
               and isinstance(node.value.value, str):
                continue
            lines.add(node.lineno)
    return lines


def main():
    # Discovery (and therefore module import) must happen INSIDE the traced region,
    # otherwise import-time statements are never recorded and coverage is understated.
    for mod in [m for m in list(sys.modules) if m.startswith(("feeengine", "tests"))]:
        del sys.modules[mod]

    tracer = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix, sys.exec_prefix])

    def run_all():
        loader = unittest.TestLoader()
        suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        unittest.TextTestRunner(verbosity=0).run(suite)

    tracer.runfunc(run_all)

    counts = tracer.results().counts  # {(filename, lineno): hits}
    hit_by_file = {}
    for (filename, lineno), n in counts.items():
        hit_by_file.setdefault(os.path.basename(filename), set()).add(lineno)

    print("\nMeasured statement coverage (stdlib trace)")
    print("-" * 62)
    print(f"{'module':<16}{'stmts':>7}{'covered':>9}{'missed':>8}{'coverage':>12}")
    print("-" * 62)
    total_s = total_c = 0
    for name in TARGETS:
        path = ROOT / "feeengine" / name
        if not path.exists():
            continue
        expected = executable_lines(path)
        hit = hit_by_file.get(name, set()) & expected
        stmts, cov = len(expected), len(hit)
        total_s += stmts
        total_c += cov
        pct = (cov / stmts * 100) if stmts else 0.0
        print(f"{name:<16}{stmts:>7}{cov:>9}{stmts-cov:>8}{pct:>11.1f}%")
    print("-" * 62)
    overall = (total_c / total_s * 100) if total_s else 0.0
    print(f"{'TOTAL':<16}{total_s:>7}{total_c:>9}{total_s-total_c:>8}{overall:>11.1f}%")

    refactored = [n for n in TARGETS if n != "legacy.py"]
    r_s = r_c = 0
    for name in refactored:
        path = ROOT / "feeengine" / name
        expected = executable_lines(path)
        hit = hit_by_file.get(name, set()) & expected
        r_s += len(expected); r_c += len(hit)
    print(f"\nRefactored package only: {r_c}/{r_s} = {(r_c/r_s*100):.1f}%")
    leg = ROOT / "feeengine" / "legacy.py"
    le = executable_lines(leg); lh = hit_by_file.get("legacy.py", set()) & le
    print(f"Legacy baseline only   : {len(lh)}/{len(le)} = {(len(lh)/len(le)*100):.1f}%")


if __name__ == "__main__":
    main()
