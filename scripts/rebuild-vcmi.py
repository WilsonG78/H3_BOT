"""Rebuild an already configured local VCMI tree using its cached CMake tool."""

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("Jobs must be positive")
    build = Path(__file__).resolve().parents[1] / "work/vcmi-build"
    cache = build / "CMakeCache.txt"
    if not cache.exists():
        parser.error("Configure VCMI first; see docs/LOCAL_VCMI_BUILD.md")
    cmake = shutil.which("cmake")
    if not cmake:
        for line in cache.read_text().splitlines():
            if line.startswith("CMAKE_COMMAND:INTERNAL="):
                candidate = line.split("=", 1)[1]
                if Path(candidate).is_file():
                    cmake = candidate
                break
    if not cmake:
        parser.error("Install CMake >= 3.21 and Ninja; the cached CMake tool is unavailable")
    raise SystemExit(subprocess.call([cmake, "--build", str(build), "--parallel", str(args.jobs)]))


if __name__ == "__main__":
    main()
