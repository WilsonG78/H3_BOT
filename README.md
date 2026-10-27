# H3 Bot

A VCMI bridge for a Python application with a custom battle RL policy, an LLM
strategist, and a System 1 executor. Model decisions stay outside the engine.

Currently implemented: a partial battle-state contract, a C++ observer/controller,
a Python service, and a terminal state inspector. RL training, automatic episode
reset, and adventure-map integration are not implemented yet.

## Requirements and platform status

- Python 3.11+ and uv; the default development version is Python 3.12.
- C++ builds: CMake >= 3.21, Ninja, and a compatible compiler.
- Engine integration: VCMI 1.6.5 sources with our player-interface hook.
- Original Heroes III Complete / Shadow of Death data supplied by each user.

Target platforms are Windows, Linux, and macOS. The full modified engine has
been built and startup-tested on Debian 13 only. Windows/macOS engine builds and
real battle observation/control still need verification. Prebuilt cross-platform
packages are not available yet.

## First-time setup

Start with the [fresh-clone setup guide](docs/SETUP.md), including downloads and
original game data. Platform-specific build and launch instructions:

- [Windows 10/11 x64](docs/SETUP_WINDOWS.md)
- [macOS: Apple Silicon and Intel](docs/SETUP_MACOS.md)
- [Debian 13 / Linux](docs/SETUP_LINUX.md)

Windows/macOS procedures are documented but not yet executed on those platforms.
They are not prebuilt packages. The prepared Linux build is local and is not
included in a clone.

## Python setup and offline preview

Run commands from the repository root:

```bash
uv sync --locked
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --once
```

The example is synthetic and works without VCMI. To inspect its raw mapped JSON:

```bash
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --json
```

Use `uv add package-name` for dependencies and `uv add --dev package-name` for
development tools. Commit `uv.lock`. No manual virtual-environment activation
is required.

## Run the game and inspect battle state

These commands require the **locally rebuilt VCMI client**, not the standard
installed game. The prepared Linux build lives in `work/vcmi-build/bin/` on the
original development machine. That directory is ignored by Git: a fresh clone
must first prepare its own engine build using the [adapter guide](docs/VCMI_ADAPTER.md).
See [local Linux build notes](docs/LOCAL_VCMI_BUILD.md) for the existing setup.

Open three terminals in the repository root and keep each process running.

**Terminal 1 — receive observations:**

```bash
uv run h3-battle-server --mode observe
```

**Terminal 2 — inspect the latest mapped state:**

```bash
uv run h3-battle-watch
```

**Terminal 3 — launch the local rebuilt game:**

```bash
uv run python scripts/run-vcmi.py --mode observe
```

Start a map, enter a manual battle, and disable quick/auto combat. The bridge
publishes snapshots at battle start, round start, action completion, stack
activation, and battle end. The inspector shows stacks, HP, current statistics,
positions, event status, and observation age.

The launcher script sets the engine working directory and local Linux SDK path.
For another machine or build layout, use the platform-specific environment and
launch instructions in the adapter guide. It is not a universal packaged-game
launcher yet.

The latest snapshot is `runs/latest-battle.json`; received events and requested
actions are recorded in `runs/battle-decisions.jsonl`. These files are private
local outputs and are ignored by Git. Before the first snapshot the inspector
shows a waiting message. After a disconnect the last snapshot may remain: check
its timestamp and status. Press `Ctrl+C` to stop the Python tools.

### Observation versus external control

| Mode | Who chooses actions? | Bridge behavior |
| --- | --- | --- |
| `observe` | Human using the game UI | Sends telemetry in the background; never requests an action |
| `control` | Your Python code / custom RL policy | Requests an offered action ID; submits only the external choice |

To debug external control, use `--mode control` on both the server and game
launcher. The CLI service then asks for action IDs interactively. A custom policy
uses `DecisionServer(port, policy=my_policy, mode="control")`.

The bridge is independent of BattleAI. A control failure leaves the current
decision unresolved and reports an environment error; it never selects a
defense fallback or delegates the controlled decision to a built-in policy.
Initial control support covers basic stack actions on open fields. Spells,
sieges, tactics, automatic reset, and a complete RL `reset()`/`step()` interface
are future work. Ordinary opponents can still use the game's existing AI.

## Build and rebuild

The root CMake project builds the standalone transport, not the full game:

```bash
cmake --preset debug -DH3_BUILD_TEST_TOOLS=ON
cmake --build --preset debug
```

A `release` preset is also available. Use GCC/Clang on Linux, Apple Clang on macOS,
or MSVC in a Developer PowerShell on Windows. Local overrides belong in the
ignored `CMakeUserPresets.json`.

For the already configured local VCMI engine:

```bash
uv run python scripts/rebuild-vcmi.py --jobs 2
```

Normal game launches and Python/model changes do not require C++ compilation.
After changing C++, rebuild and restart the game. Ninja recompiles affected
files and their dependencies; keep the build directory to reuse prior results.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

Tests need permission to open local sockets. Native integration tests are skipped
unless `H3_BRIDGE_PROBE` points to the compiled probe. See the
[adapter guide](docs/VCMI_ADAPTER.md) for platform-specific probe paths.

After changing contract models, regenerate and review the JSON schemas:

```bash
uv run python scripts/export-battle-schemas.py
```

## Repository layout

```text
adapters/vcmi/       C++ transport and VCMI player-interface integration
protocol/            versioned JSON schemas
src/h3_bot/
  domain/            battle, adventure-map, and catalog models
  vcmi/              Python receiver, control service, and inspector
  battle/rl/         planned custom battle RL implementation
  strategy/llm/      planned strategic planner
  execution/         planned System 1 executor
  orchestration/     planned coordination between decision modules
  telemetry/         planned reusable recording/analysis logic
data/fixtures/      synthetic observations for offline development
data/local/         private data (ignored)
patches/             upstream compatibility fixes
scripts/             schema, integration, build, and launch utilities
tests/               contract and transport tests
docs/                setup, architecture, and implementation plan
runs/                generated snapshots/logs/checkpoints (ignored)
work/                downloaded sources, SDK, and engine builds (ignored)
```

The domain layer has no VCMI or ML-library dependency. Python decision modules
consume our models; engine-specific extraction and action submission stay in C++.

## Documentation

- [Setup from scratch and downloads](docs/SETUP.md)
- [Adapter setup, protocol, and limitations](docs/VCMI_ADAPTER.md)
- [Battle inspector](docs/BATTLE_INSPECTOR.md)
- [Local Linux build and launch](docs/LOCAL_VCMI_BUILD.md)
- [Battle prototype scenario](docs/BATTLE_PROTOTYPE.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)

All repository content is written in English. Keep original game assets, private
saves, credentials, downloaded dependencies, binaries, and training results out
of commits.
