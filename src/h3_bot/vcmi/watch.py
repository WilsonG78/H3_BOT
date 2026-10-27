"""Read-only terminal inspector for the latest mapped battle observation."""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from h3_bot.domain.battle.models import BattleObservation


def load(path: Path) -> tuple[BattleObservation, datetime | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "observation" in payload:
        received = datetime.fromisoformat(payload["received_at"])
        if received.tzinfo is None:
            raise ValueError("Snapshot timestamp must include a timezone")
        return BattleObservation.model_validate(payload["observation"]), received
    return BattleObservation.model_validate(payload), None


def render(observation: BattleObservation, received: datetime | None) -> str:
    age = "offline fixture / timestamp unavailable"
    if received:
        seconds = max(0, int((datetime.now(timezone.utc) - received).total_seconds()))
        age = f"received {seconds}s ago at {received.astimezone().isoformat(timespec='seconds')}"
    lines = [
        "H3 BATTLE INSPECTOR | READ ONLY",
        "Latest received battle event; not a continuous live game feed.",
        f"Source: {observation.engine}",
        f"Mode: {observation.mode} | Event: {observation.event} | Status: {observation.status}",
        f"Winner side: {observation.winner_side} | Error: {observation.error or 'none'}",
        f"Snapshot: {age}",
        f"Battle: {observation.battle_id}",
        f"Round: {observation.round} | Decision: {observation.decision_id} | Revision: {observation.revision}",
        f"Viewer side: {observation.viewer_side} | Active stack: {observation.active_stack_id}",
        "",
    ]
    rows = [["Active", "ID", "Side", "Creature", "Count", "Top HP", "Total HP", "Hex", "Atk M/R", "Def M/R", "Move", "Shots", "Status"]]
    for stack in observation.stacks:
        status = [name for name in ["waited", "moved", "defended"] if getattr(stack.turn_status, name)]
        if not stack.alive:
            status.append("dead")
        if stack.ghost:
            status.append("ghost")
        rows.append([
            "*" if stack.id == observation.active_stack_id else "",
            str(stack.id), str(stack.side_id), stack.creature_id, str(stack.count),
            f"{stack.top_unit_hp}/{stack.max_unit_hp}", str(stack.total_hp), str(stack.position),
            f"{stack.stats.attack_melee}/{stack.stats.attack_ranged}",
            f"{stack.stats.defense_melee}/{stack.stats.defense_ranged}",
            str(stack.stats.movement_range), str(stack.shots), ",".join(status) or "ready",
        ])
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        lines.append("  ".join(value.ljust(width) for value, width in zip(row, widths)))
    lines += ["", "BATTLEFIELD (VCMI row-major hex IDs; A=side 0, D=side 1, #=blocked)"]
    field = observation.battlefield
    cells = {hex_id: "#" for obstacle in field.obstacles for hex_id in obstacle.blocked_hexes}
    for stack in observation.stacks:
        if stack.alive and not stack.ghost:
            for hex_id in stack.occupied_hexes:
                cells[hex_id] = f"{'A' if stack.side_id == 0 else 'D'}{stack.id}"
    width = max(4, max((len(value) for value in cells.values()), default=1) + 1)
    for y in range(field.height):
        row = []
        for x in range(field.width):
            hex_id = y * field.width + x
            row.append(cells.get(hex_id, "|" if x in [0, field.width - 1] else ".").rjust(width))
        lines.append(f"{y:02d}: " + (" " * (width // 2) if y % 2 else "") + "".join(row))
    lines += ["", f"OFFERED ACTIONS ({len(observation.legal_actions)}; supported subset)"]
    for action in observation.legal_actions:
        lines.append(action.model_dump_json())
    lines += ["", "Snapshots can be stale after disconnect; check event, status, and timestamp.",
              "Spells, heroes, effects, and adventure-map state are not exported yet."]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=Path("runs/latest-battle.json"))
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--once", action="store_true", help="Print once and exit")
    parser.add_argument("--json", action="store_true", help="Print raw mapped observation once and exit")
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < 0.1:
        parser.error("Interval must be finite and at least 0.1 seconds")
    if not (args.once or args.json) and not sys.stdout.isatty():
        parser.error("Watch mode requires a terminal; use --once or --json for redirected output")
    try:
        while True:
            success = True
            try:
                observation, received = load(args.file)
                output = observation.model_dump_json(indent=2) if args.json else render(observation, received)
            except FileNotFoundError:
                success = False
                output = (f"Waiting for a battle observation: {args.file}\n"
                          "Start h3-battle-server and a rebuilt VCMI client with the bridge enabled.\n"
                          "The installed unmodified game does not publish observations.")
            except (OSError, ValueError, KeyError, TypeError) as error:
                success = False
                output = f"Cannot read battle observation: {error}"
            if args.json:
                if not success:
                    print(output, file=sys.stderr)
                    raise SystemExit(1)
            elif not args.once:
                # Enable virtual-terminal output where required by Windows consoles.
                if sys.platform == "win32":
                    import os
                    os.system("")
                print("\033[2J\033[H", end="")
            print(output, flush=True)
            if args.once or args.json:
                if not success:
                    raise SystemExit(1)
                return
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
