import os, sys, inspect, importlib

os.environ['LINEWORK_MEMORY'] = '0'
sys.path.insert(0, os.path.abspath('.'))

test_modules = [
    'tests.test_topology',
    'tests.test_rings',
    'tests.test_budget',
    'tests.test_repair',
    'tests.test_finisher',
    'tests.test_lessons',
    'tests.test_joints',
    'tests.test_structfix',
]

total = 0
failed = 0
for mod_name in test_modules:
    print(f"\n--- {mod_name} ---")
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:
        print(f"FAILED TO IMPORT {mod_name}: {e}")
        failed += 1
        continue
    funcs = [getattr(mod, name) for name in dir(mod) if name.startswith('test_') and callable(getattr(mod, name))]
    for fn in funcs:
        total += 1
        try:
            fn()
            print(f"  PASS: {fn.__name__}")
        except Exception as e:
            print(f"  FAIL: {fn.__name__}: {e}")
            failed += 1

print(f"\nSummary: {total - failed}/{total} passed. {failed} failed.")
if failed:
    sys.exit(1)
