"""Tiny test runner (pytest is not installed here): runs every test_* function / unittest case of the quick test modules."""
import sys, os, importlib, inspect, time, traceback, unittest
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("LINEWORK_MEMORY", "0")
SKIP = {"test_100_ultra_complex_suite", "test_100_icons_job", "test_heavy_joins_suite", "test_user_sheet_24", "test_acceptance_load",
        "test_1000_icons_splitting_and_sampling", "test_cancellation_and_cache"}
only = set(sys.argv[1:])
tot = bad = 0
for f in sorted((root / "tests").glob("test_*.py")):
    name = f.stem
    if name in SKIP or (only and name not in only):
        continue
    try:
        mod = importlib.import_module(f"tests.{name}")
    except BaseException as e:
        print(f"IMPORT-FAIL {name}: {e!r}")
        bad += 1
        continue
    for fn_name, fn in inspect.getmembers(mod, inspect.isfunction):
        if fn_name.startswith("test_") and fn.__module__ == mod.__name__ and not inspect.signature(fn).parameters:
            t = time.time(); tot += 1
            try:
                fn()
                print(f"ok   {name}.{fn_name} ({time.time()-t:.1f}s)", flush=True)
            except BaseException:
                bad += 1
                print(f"FAIL {name}.{fn_name}\n{traceback.format_exc(limit=3)}", flush=True)
    for cn, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, unittest.TestCase) and cls.__module__ == mod.__name__:
            res = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
            tot += res.testsRun
            bad += len(res.failures) + len(res.errors)
print(f"\nTOTAL {tot} tests, {bad} failed")
