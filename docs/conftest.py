"""Pytest configuration file needs to be here to be able to test README.md

All other configuration is done in tests/conftest.py
"""

from sybil import Sybil
from sybil.parsers.myst import PythonCodeBlockParser

pytest_collect_file = Sybil(
    parsers=[PythonCodeBlockParser()], pattern="*.md", fixtures=[]
).pytest()
