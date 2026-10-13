"""Pytest configuration.

An empty conftest.py at the project root is enough to put this directory on
sys.path, which is what lets tests/test_pawpal.py do `from pawpal_system
import ...` even though it lives one level down.

Without it, `pytest` only works when run as `python -m pytest` (which adds the
current directory to sys.path itself). This way both commands work.
"""
