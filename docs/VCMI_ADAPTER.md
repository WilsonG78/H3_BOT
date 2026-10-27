# Player bridge: observation and external control

## Architecture

VCMI 1.6.5 player interface → adapter C++ → TCP/NDJSON → Python application.
Only explicit control decisions have an action reply. The adapter never chooses
an action. It does not depend on BattleAI or call its evaluator or strategy.

The integration is in `client/CPlayerInterface.cpp`, linked to
`vcmiclientcommon`. `ExternalBattleController` is our adapter-only controller.
Existing VCMI AI for OTHER players/neutral opponents is not replaced. To control
both sides, both must be local human player interfaces; headless AI-only play is
not supported by this hook yet.

## Modes

- `H3_BOT_MODE=off` (or unset): no bridge activity.
- `H3_BOT_MODE=observe`: manual play; snapshots copied on battle start, round
  start, action finish, actor activation, and battle end. A bounded background
  publisher sends snapshots without waiting for Python or submitting actions.
- `H3_BOT_MODE=control`: Python owns the local human player's stack decisions.
  Quick combat is disabled for that interface. A decision callback submits
  exactly the action selected externally, or NO action on an error. There is no
  defense fallback and no transfer to a built-in AI strategy.

Use normal manual battle mode; do not enable auto-combat when observing manual
play. In control mode, do not toggle auto-combat or manually issue battle actions.
No hooks are installed in `AI/BattleAI`. The setup script removes the exact
legacy BattleAI patch if detected, refusing to overwrite unfamiliar edits.

## Setup

For a fresh machine, follow the [platform setup guides](SETUP.md) first.

Install Python/uv, CMake >= 3.21, Ninja, and a compiler. Use compatible upstream
VCMI tag `1.6.5` sources and follow that release's build-dependency instructions.
From this repository:

```bash
uv sync --locked
uv run python scripts/enable-vcmi-bridge.py --source /path/to/vcmi
```

Review the source diff and build VCMI with its client enabled. Use the rebuilt
client and matching libraries together; the installed game remains unchanged.
The patch references this repository by absolute path, so keep it in place.
Applying it again is a no-op. Do not commit downloaded sources or game assets.

### Manual play with observation

Terminal 1:

```bash
uv run h3-battle-server --mode observe
```

Terminal 2:

```bash
uv run h3-battle-watch
```

Linux/macOS game launch:

```bash
H3_BOT_MODE=observe H3_BOT_PORT=8765 /path/to/rebuilt/vcmiclient
```

Windows Developer PowerShell:

```powershell
$env:H3_BOT_MODE = "observe"
$env:H3_BOT_PORT = "8765"
& "C:\path\to\rebuilt\VCMI_client.exe"
```

Start a manual battle. Receiving observations never invokes a Python policy or
waits for a response. Network errors are logged in the publisher thread and
manual gameplay continues. The queue holds 64 copied snapshots; overflow drops
the oldest snapshot with a diagnostic. It is telemetry, not a lossless replay.
Only snapshot extraction itself runs on the game callback.

### External control / custom RL

Set `H3_BOT_MODE=control` for the game process and run:

```bash
uv run h3-battle-server --mode control
```

The CLI requests an action ID interactively as an integration/debugging tool.
A model supplies its own callable using
`DecisionServer(port, policy=my_policy, mode="control")`. The callable receives
`BattleObservation` and returns one offered action ID. It is the only place
where action selection belongs. There is no built-in default combat policy.

Control decisions wait up to the transport's 30-second socket timeout. The UI
interface mutex is released while waiting. On connection failure, invalid/stale
reply, unsupported scenario, or policy error, the adapter reports an environment
error and returns without issuing a fallback move. The current decision is left
unresolved; the episode is halted. Reload/restart the test scenario to recover;
retry/resume and automatic reset are not implemented. A reachable receiver gets
an `environment_error` snapshot; when it is unreachable, the game stderr remains
the diagnostic source. Error reporting does not guarantee delivery.

Initial control scope: basic stack actions on open fields. Tactics, sieges, and
siege-weapon actors halt control with an unsupported-scenario error. They do not
fall through to an existing policy. Manual observation is broader but still
exports only our partial model. Supported offered actions are defense, wait,
move, shoot, and melee attack; this is not the complete VCMI action space.

## Protocol version 2

Each connection carries one bounded UTF-8 JSON line, maximum 4 MiB. The Python
service listens only on `127.0.0.1:8765`. There is no authentication; use trusted
local processes. C++ uses Winsock on Windows and POSIX sockets on Linux/macOS.

Observation fields include:

- `schema_version=2`, process-scoped `battle_id`, monotonic snapshot `revision`.
- `mode`: observe/control.
- `event`: battle_started, round_started, action_finished, decision,
  battle_ended, or environment_error.
- `status`: running, terminated, or error; optional `winner_side` and `error`.
- Nullable `active_stack_id`; an empty `legal_actions` list for non-control
  events. Only running control decisions request replies.
- Stack positions, counts, health, current melee/ranged stats, turn flags,
  shots, and visible blocked obstacle hexes.

Action replies must echo schema, battle, revision, and decision IDs and select
an offered action ID. C++ stores the native VCMI action; Python does not submit
arbitrary engine parameters. VCMI is still the final legality authority.

The receiver publishes `runs/latest-battle.json` BEFORE invoking a control
policy. Logs contain received events and requested actions, not authoritative
server acceptance. Out-of-order telemetry cannot overwrite newer snapshots;
an error for the current decision can update its status.

Base creature definitions and complete effects are not exported yet. Effective
`owner` can differ from original `side_id` under mind control. Hex indices retain
VCMI's row-major 17×11 layout; edge columns are not ordinary movement cells.
Dead/ghost stack positions do not imply blocked cells. `round` preserves VCMI
numbering. Snapshot counters are not revisions for every engine mutation.

Battle-end events allow a receiver to detect episode completion. Full reset/step
semantics, correlated action acknowledgements/rejections, deterministic reset,
reward computation, and high-throughput training are still future work. This is
an observation/control adapter, not yet a complete RL environment.

## Verification and build commands

Verified on Linux: standalone transport build, C++/Python exchange, observer
publication without a reply, contract tests, and syntax checks of the controller
and patched player-interface translation units against VCMI 1.6.5 sources.
The complete modified engine builds locally on Debian 13; the client runs with
`--version`, its bridge symbols are present, and runtime dependencies resolve.
Actual battle gameplay and observation capture are not yet verified.
Windows/macOS code paths are not yet tested.

```bash
cmake --preset debug -DH3_BUILD_TEST_TOOLS=ON
cmake --build --preset debug
uv run python -m unittest discover -s tests -v
```

CMake downloads SHA-256-pinned nlohmann/json 3.11.3. For offline builds, pass
`-DFETCHCONTENT_SOURCE_DIR_JSON=/path/to/extracted/json`. This builds the transport
and probe, not VCMI. Set `H3_BRIDGE_PROBE` to the absolute built probe path to run
native integration tests; add `.exe` on Windows. Tests require local sockets.

Regenerate schemas using `uv run python scripts/export-battle-schemas.py`.
Synthetic examples are in `data/fixtures/`; they are not captured game data.
See [inspector guide](BATTLE_INSPECTOR.md).
