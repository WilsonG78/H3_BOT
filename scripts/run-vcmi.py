"""Launch the locally rebuilt VCMI client with an explicit bridge mode."""

import argparse
import os
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["off", "observe", "control"], default="observe")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("game_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be in range 1..65535")
    root = Path(__file__).resolve().parents[1]
    binary_dir = root / "work/vcmi-build/bin"
    binary = binary_dir / ("VCMI_client.exe" if os.name == "nt" else "vcmiclient")
    if not binary.is_file():
        parser.error(f"Rebuilt client does not exist: {binary}")
    env = os.environ.copy()
    env["H3_BOT_MODE"] = args.mode
    env["H3_BOT_PORT"] = str(args.port)
    sdk = root / "work/vcmi-sdk/usr/lib/x86_64-linux-gnu"
    if os.name != "nt" and sdk.is_dir():
        env["LD_LIBRARY_PATH"] = str(sdk) + (os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    extra = args.game_args
    if extra[:1] == ["--"]:
        extra = extra[1:]
    # VCMI development mode discovers matching configs, server, and AI in this cwd.
    raise SystemExit(subprocess.call([str(binary), *extra], cwd=binary_dir, env=env))


if __name__ == "__main__":
    main()
