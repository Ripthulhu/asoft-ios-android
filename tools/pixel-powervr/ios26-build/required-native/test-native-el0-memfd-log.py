#!/usr/bin/env python3
"""Exercise the actual phone script's result checker against synthetic logs."""
from pathlib import Path
import json
import re
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/native-el0-memfd-smoke.sh"

GOOD = """native-el0: required initialization ready mode=stubs; guest execution not yet observed
T6 OK calls=1000 fpcr=0x0 arith=0x55
T10 memcpy16 bytes=16777216 reps=20 ns=1000000 ticks=19200 MBps=320000 check=ok
EXIT 0 faults=3 irqs=4
native-el0: enters 100 svc 40 fills 3 (failed 0) faults-injected 0
native-el0: stubs 2 spawned 1 bound 1 evictions 0
native-el0: time native 8 ms, trap handling 2 ms, entry 0 ms (wall since first vCPU 12 ms)
"""


def main():
    source = SCRIPT.read_text()
    functions = []
    for name in ("fail", "check_benchmark_log"):
        match = re.search(r"^" + name + r"\(\) \{\n.*?^\}\n", source, re.M | re.S)
        if not match:
            raise RuntimeError(f"Missing production shell function: {name}")
        functions.append(match.group())
    cases = [
        ("lowercase-ok", GOOD, True),
        ("copy-BAD", GOOD.replace("check=ok", "check=BAD"), False),
        ("uppercase-OK-is-not-guest-output", GOOD.replace("check=ok", "check=OK"), False),
        ("copy-BAD-alongside-ok", GOOD + "T10 memcpy16 bytes=16 reps=1 check=BAD\n", False),
        ("zero-native-SVC", GOOD.replace("enters 100 svc 40", "enters 100 svc 0"), False),
        ("zero-native-time", GOOD.replace("time native 8 ms", "time native 0 ms"), False),
        ("guest-incomplete", GOOD.replace("EXIT 0 faults=3 irqs=4\n", ""), False),
        ("floating-point-mismatch", GOOD + "T6 MISMATCH fpcr got=0x1 want=0x0\n", False),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="native-memfd-log-") as temp:
        root = Path(temp)
        harness = root / "checker.sh"
        harness.write_text("set -eu\n" + "\n".join(functions) +
                           'bench_results=$2\ncheck_benchmark_log "$1"\n'
                           "printf 'NATIVE_MEMFD_BENCH_PASS=1\\n'\n")
        for name, log, expected in cases:
            path = root / (name + ".txt")
            path.write_text(log)
            run = subprocess.run(["sh", str(harness), str(path), str(root)],
                                 capture_output=True, text=True, timeout=2)
            assert run.returncode == (0 if expected else 1), (name, run)
            assert ("NATIVE_MEMFD_BENCH_PASS=1" in run.stdout) == expected, (name, run)
            assert ("NATIVE_MEMFD_BENCH_PASS=0" in run.stdout) != expected, (name, run)
            results.append({"name": name, "expected_pass": expected,
                            "exit_code": run.returncode, "pass": True})
    print(json.dumps({"scope": "actual phone-script checker with synthetic logs", "cases": results}, indent=2))


if __name__ == "__main__":
    main()
