#!/usr/bin/env python3
from pathlib import Path
import os
import sys
root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["PKG_CONFIG_LIBDIR"] = os.pathsep.join([
    str(root / "target-pkgconfig"),
    str(root / "reims-dist/lib/pkgconfig"),
])
env["PKG_CONFIG_PATH"] = ""
env.pop("PKG_CONFIG_SYSROOT_DIR", None)
os.execve("/usr/bin/pkg-config", ["pkg-config", *sys.argv[1:]], env)
