"""Run the whole test suite as isolated subprocesses.

Each test module owns its temp DB and process state, so they can be run in
any order without interfering with each other (parallelization-friendly).

Run:  python tests/run_all.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = [
    "core_rules.py",
    "managers.py",
    "web_e2e.py",
    "framework_shared.py",
    "realtime_sse.py",
]


def main():
    failed = []
    for name in TESTS:
        path = os.path.join(HERE, name)
        print(f"--- {name} ---")
        p = subprocess.run([sys.executable, path])
        if p.returncode != 0:
            failed.append(name)
            print(f"FAILED: {name}")

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    print(f"ALL {len(TESTS)} TEST MODULES PASSED")


if __name__ == "__main__":
    main()
