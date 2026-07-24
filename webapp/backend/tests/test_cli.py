"""End-to-end CLI tests: run `python -m diagen` as a subprocess against the
real fixture workbooks, the way a manager actually invokes this tool."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

from .conftest import DIAGEN_PKG_DIR, SPEC_XLSX, TEMPLATE_XLSX, EXAMPLES_DIR


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, '-m', 'diagen', *args],
        cwd=cwd or DIAGEN_PKG_DIR, capture_output=True, text=True,
        env={'PYTHONPATH': str(DIAGEN_PKG_DIR), 'PATH': '/usr/bin:/bin'})


def test_cli_renders_every_sample_diagram(tmp_path):
    out = tmp_path / 'out'
    r = run_cli(str(SPEC_XLSX), '-o', str(out))
    assert r.returncode == 0, r.stderr
    svgs = list(out.glob('*.svg'))
    assert len(svgs) >= 4  # D1..D5 minus any without sample data
    assert (out / 'index.html').exists()


def test_cli_renders_authoring_template_standalone(tmp_path):
    """The file a manager actually fills in should render with no other
    inputs - this is the whole point of the tool."""
    out = tmp_path / 'out'
    r = run_cli(str(TEMPLATE_XLSX), '-o', str(out))
    assert r.returncode == 0, r.stderr
    assert list(out.glob('*.svg'))


def test_cli_diagram_filter_renders_only_requested(tmp_path):
    out = tmp_path / 'out'
    r = run_cli(str(SPEC_XLSX), '-o', str(out), '--diagram', 'D2')
    assert r.returncode == 0, r.stderr
    svgs = {p.name for p in out.glob('*.svg')}
    assert svgs == {'D2.svg'}


def test_cli_format_svg_only_skips_drawio(tmp_path):
    out = tmp_path / 'out'
    r = run_cli(str(SPEC_XLSX), '-o', str(out), '--diagram', 'D2', '--format', 'svg')
    assert r.returncode == 0, r.stderr
    assert (out / 'D2.svg').exists()
    assert not (out / 'D2.drawio').exists()


def test_cli_external_csv_overrides_workbook_sample_data(tmp_path):
    out = tmp_path / 'out'
    r = run_cli(str(SPEC_XLSX), '-o', str(out),
                '--nodes', str(EXAMPLES_DIR / 'nodes.csv'),
                '--edges', str(EXAMPLES_DIR / 'edges.csv'))
    assert r.returncode == 0, r.stderr
    assert (out / 'D2.svg').exists()


def test_cli_missing_spec_file_fails_with_nonzero_exit(tmp_path):
    r = run_cli(str(tmp_path / 'does_not_exist.xlsx'), '-o', str(tmp_path / 'out'))
    assert r.returncode != 0
