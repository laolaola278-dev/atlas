"""Discover and run every Python test module in the repository.

CI and the evidence index both call this, so there is exactly one module list
and it cannot drift from what is on disk. Discovery is explicit rather than
unittest's own: these packages have no __init__.py, so unittest discover finds
nothing here.

Usage:
    python -B tools/evidence/python_gates.py           # run everything
    python -B tools/evidence/python_gates.py --list    # print the module list
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRECTORIES = frozenset({".git", ".venv", "__pycache__", "_scratch", "build", "dist", "node_modules"})
_MINIMUM_MODULES = 79


def discover_modules(root: Path = _ROOT) -> tuple[str, ...]:
    """Return every test module name under root, sorted."""
    found: list[str] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SKIP_DIRECTORIES)
        for filename in sorted(filenames):
            if not filename.startswith("test_") or not filename.endswith(".py"):
                continue
            relative = (Path(directory) / filename).relative_to(root)
            found.append(".".join(relative.with_suffix("").parts))
    return tuple(sorted(found))


def main() -> int:
    """Run the discovered suite and propagate its exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print the discovered modules and exit")
    parser.add_argument("--extra", action="append", default=[], help="run one extra module as well")
    args = parser.parse_args()
    modules = list(discover_modules())
    modules.extend(args.extra)
    if args.list:
        print("\n".join(modules))
        print(f"modules={len(modules)}")
        return 0
    if len(modules) < _MINIMUM_MODULES:
        print(f"MODULE DISCOVERY REGRESSED: found {len(modules)}, expected at least {_MINIMUM_MODULES}")
        return 1
    print(f"running {len(modules)} test modules")
    done = subprocess.run([sys.executable, "-B", "-m", "unittest", *modules], cwd=_ROOT)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
