"""Ensures the package under test is importable when pytest runs from the repository root."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
