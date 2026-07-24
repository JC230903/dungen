"""Shared fixtures for the diagen test suite.

Uses the real spec workbook (fixtures/Diagram_Automation_CSV_Spec.xlsx) and
the example CSVs (../examples) as fixtures instead of hand-rolled mocks, so
tests exercise the actual authoring data managers will use.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent          # webapp/backend — diagen/ and app/ both live here
sys.path.insert(0, str(BACKEND_DIR))

SPEC_XLSX = TESTS_DIR / 'fixtures' / 'Diagram_Automation_CSV_Spec.xlsx'
TEMPLATE_XLSX = TESTS_DIR / 'fixtures' / 'Diagram_Authoring_Template.xlsx'
EXAMPLES_DIR = BACKEND_DIR / 'examples'

# kept for test_cli.py, which shells out `python -m diagen` and needs the
# directory that has `diagen/` as an importable sibling package on PYTHONPATH
DIAGEN_PKG_DIR = BACKEND_DIR


@pytest.fixture(scope='session')
def spec_path():
    assert SPEC_XLSX.exists(), f'fixture workbook missing: {SPEC_XLSX}'
    return SPEC_XLSX


@pytest.fixture()
def spec(spec_path):
    from diagen.spec import Spec
    return Spec(spec_path)


@pytest.fixture()
def template_spec():
    from diagen.spec import Spec
    assert TEMPLATE_XLSX.exists(), f'fixture workbook missing: {TEMPLATE_XLSX}'
    return Spec(TEMPLATE_XLSX)
