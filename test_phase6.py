r"""test_phase6.py - checks the final-build helpers (Phase 6): self-test and start with Windows.
Uses a temporary folder, so it never touches your real data. The start-with-Windows checks use a
test entry in the registry and remove it again; they are skipped on other systems.

Run:  .venv\Scripts\python test_phase6.py
"""
import sys
import tempfile
import traceback
from pathlib import Path

import selftest
import winstartup

TMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
ROOT = Path(TMP.name)
TEST_NAME = "OfficeDocumentArchive_test_entry"
TEST_CMD = r'"C:\Program Files\Example\OfficeArchive.exe"'


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def t_selftest_passes():
    results = selftest.run_checks()
    names = [r[1] for r in results]
    assert names[:4] == ["libraries", "window toolkit", "archive", "browser view"], names
    bad = [r for r in results if r[0] == "FAIL"]
    assert not bad, bad


def t_selftest_report_file():
    out = ROOT / "report.txt"
    assert selftest.run(out) == 0
    text = out.read_text(encoding="utf-8")
    assert "PASS  archive" in text and "SELF-TEST PASSED" in text, text


def t_selftest_reports_failure():
    out = ROOT / "report_fail.txt"

    def boom():
        raise RuntimeError("deliberate")
    assert selftest.run(out, extra_checks=[("deliberate failure", boom)]) == 1
    text = out.read_text(encoding="utf-8")
    assert "FAIL  deliberate failure: RuntimeError: deliberate" in text and "SELF-TEST FAILED (1 problem(s))" in text


def t_selftest_does_not_touch_real_data():
    import storage
    real = storage.default_data_dir()
    before = sorted(p.name for p in real.glob("*")) if real.exists() else None
    selftest.run_checks()
    after = sorted(p.name for p in real.glob("*")) if real.exists() else None
    assert before == after, (before, after)


def t_startup_not_built():
    # from source (not the .exe) there is nothing to register, and it says so plainly
    if getattr(sys, "frozen", False):
        return
    assert winstartup.is_enabled() is False
    assert raises(winstartup.StartupError, winstartup.enable)


def t_startup_registry():
    if not sys.platform.startswith("win"):
        print("      (skipped: not Windows)")
        return
    try:
        assert winstartup.is_enabled(TEST_CMD, TEST_NAME) is False
        winstartup.enable(TEST_CMD, TEST_NAME)
        assert winstartup.is_enabled(TEST_CMD, TEST_NAME) is True
        assert winstartup.is_enabled(r'"D:\Elsewhere\OfficeArchive.exe"', TEST_NAME) is False   # moved program: not "on"
        winstartup.disable(TEST_NAME)
        assert winstartup.is_enabled(TEST_CMD, TEST_NAME) is False
        winstartup.disable(TEST_NAME)                                                           # removing twice is harmless
    finally:
        winstartup.disable(TEST_NAME)


TESTS = [t_selftest_passes, t_selftest_report_file, t_selftest_reports_failure,
         t_selftest_does_not_touch_real_data, t_startup_not_built, t_startup_registry]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__[2:]}")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__[2:]}")
            traceback.print_exc()
    print()
    print("ALL TESTS PASSED" if not failed else f"{failed} TEST(S) FAILED")
    try:
        TMP.cleanup()
    except Exception:
        pass
    sys.exit(1 if failed else 0)
