"""Run Phase 1 unittest plus ALL eleven unmodified v1 tests in isolated cwd."""
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).parent
os.chdir(ROOT)
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_phase*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    legacy = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", "test_poc", "test_state_sync"],
                            cwd=ROOT / "legacy_v1", env=env, capture_output=True, text=True, encoding="utf-8")
    print(legacy.stdout)
    print(legacy.stderr)
    counts = re.findall(r"Ran (\d+) tests?", legacy.stderr)
    legacy_count = int(counts[-1]) if counts else 0
    print(f"Phase 1 + Phase 2A + Phase 2B: {result.testsRun}; legacy: {legacy_count}; total: {result.testsRun + legacy_count}")
    sys.exit(0 if result.wasSuccessful() and legacy.returncode == 0 and legacy_count == 11 else 1)
