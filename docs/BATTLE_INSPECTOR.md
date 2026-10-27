# Battle inspector

A read-only terminal view of the latest mapped battle event. It shows event,
mode, episode status, winner/error, receipt time, stack statistics, positions,
a schematic battlefield, and offered actions when external control is active.

## Offline preview

```bash
uv sync --locked
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --once
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --json
```

Examples are synthetic and labeled as such.

## Manual game observation

First build VCMI 1.6.5 with our player-interface hook following the
[adapter guide](VCMI_ADAPTER.md). An unmodified game does not publish state.
The modified engine is compiled locally and starts with `--version`; actual
battle gameplay and observation capture are not yet tested.

In separate terminals:

```bash
uv run h3-battle-server --mode observe
```

```bash
uv run h3-battle-watch
```

Launch the rebuilt game with `H3_BOT_MODE=observe` and `H3_BOT_PORT=8765`, then
play a normal manual battle with quick/auto combat disabled. The observer does
not require BattleAI, invoke a policy, send actions, or wait for Python. Engine
snapshots are copied and sent in the background at battle lifecycle events.

The receiver atomically publishes `runs/latest-battle.json`. The inspector reads
that file and never contacts or controls the game. For external control use
`--mode control` on the service and `H3_BOT_MODE=control` in the game; the
inspector works in either mode.

## Options

- `--once`: print once and exit.
- `--json`: print the mapped observation as JSON once and exit.
- `--file PATH`: select a snapshot or raw observation JSON file.
- `--interval 0.5`: refresh interval (minimum 0.1 seconds).
- Server `--state-file PATH`: change the publication path.
- `Ctrl+C`: stop the inspector without affecting the game.

Commands are shared across Windows, Linux, and macOS. Watch mode needs a terminal
with ANSI support. Only Linux execution has been tested.

`A` means original side 0; `D` means original side 1; the suffix is the stack ID.
`*` marks the active stack. Double-wide stacks occupy two cells. `#` marks
exported blocked obstacle hexes. The drawing is schematic.

Snapshots update on selected events, not continuously. A terminal event marks
battle completion if delivered. After a disconnect, the last file may remain;
check its timestamp and status rather than assuming the game is connected.
Telemetry can drop snapshots under load. Adventure-map state, hero details,
spells, and complete effects are not available yet.
