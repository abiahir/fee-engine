"""Minimal mutation tester built on the standard library.

Mutation testing answers the question coverage cannot: would the suite actually DETECT a
fault, or does it merely execute the line containing it? Each mutant is a single small change
to the production source. If the suite fails, the mutant is 'killed'. If it still passes, the
mutant 'survived' and names a real gap in the tests.

mutmut/PIT could not be installed in this environment, so this implements the same idea
against the operators most likely to carry pricing defects.

Usage: python3 tools/mutation_test.py
"""
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ["engine.py", "rules.py"]          # the logic that carries pricing risk

SWAPS = {
    ast.GtE: ast.Gt, ast.Gt: ast.GtE,
    ast.LtE: ast.Lt, ast.Lt: ast.LtE,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


class Mutator(ast.NodeTransformer):
    def __init__(self, target_index):
        self.target, self.seen, self.applied = target_index, 0, None

    def _maybe(self, node, mapping, attr):
        current = getattr(node, attr)
        replacement = mapping.get(type(current))
        if replacement is None:
            return node
        if self.seen == self.target:
            self.applied = (type(current).__name__, replacement.__name__, node.lineno)
            setattr(node, attr, replacement())
        self.seen += 1
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1:
            current = type(node.ops[0])
            if current in SWAPS:
                if self.seen == self.target:
                    self.applied = (current.__name__, SWAPS[current].__name__, node.lineno)
                    node.ops[0] = SWAPS[current]()
                self.seen += 1
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return self._maybe(node, ARITH, "op")


def count_mutations(source):
    m = Mutator(-1)
    m.visit(ast.parse(source))
    return m.seen


def run_suite(workdir):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=workdir, capture_output=True, text=True, timeout=120)
    return result.returncode == 0   # True => suite passed => mutant SURVIVED


def main():
    killed = survived = 0
    survivors = []
    for name in TARGETS:
        src_path = ROOT / "feeengine" / name
        source = src_path.read_text()
        total = count_mutations(source)
        print(f"{name}: {total} candidate mutations")
        for i in range(total):
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp) / "repo"
                shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
                    "_archive-java", "__pycache__", ".git", ".github"))
                tree = ast.parse(source)
                mut = Mutator(i)
                tree = mut.visit(tree)
                ast.fix_missing_locations(tree)
                if mut.applied is None:
                    continue
                (work / "feeengine" / name).write_text(ast.unparse(tree))
                if run_suite(work):
                    survived += 1
                    was, now, line = mut.applied
                    survivors.append(f"{name}:{line}  {was} -> {now}")
                else:
                    killed += 1
    total = killed + survived
    score = (killed / total * 100) if total else 0
    print("\n" + "=" * 54)
    print(f"Mutants killed   : {killed}")
    print(f"Mutants survived : {survived}")
    print(f"MUTATION SCORE   : {score:.1f}%")
    if survivors:
        print("\nSurviving mutants (each names a missing assertion):")
        for s in survivors:
            print("  -", s)
    print("=" * 54)


if __name__ == "__main__":
    main()
