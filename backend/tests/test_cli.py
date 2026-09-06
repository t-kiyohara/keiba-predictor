"""CLI failures must remain visible after real file-backed DB initialization."""

import os
import subprocess
import sys
from pathlib import Path


def test_fetch_failure_is_logged_after_migrations(tmp_path):
    script = """
import sys
from unittest.mock import patch
from app.cli import main, _log_progress

async def fail_fetch(self):
    _log_progress('fetch', 3, 7, 'regression progress marker')
    raise RuntimeError('regression failure marker')

with patch('app.cli.FetchService.execute', fail_fetch):
    sys.exit(main(['fetch']))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parent.parent,
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'cli.sqlite3'}",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "regression progress marker" in output
    assert "RuntimeError: regression failure marker" in output
    assert "Traceback (most recent call last)" in output
