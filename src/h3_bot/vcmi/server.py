"""Loopback decision service for the engine-side adapter."""

import argparse
import json
import logging
import socketserver
from collections.abc import Callable
from pathlib import Path

from h3_bot.domain.battle.models import ActionReply, BattleObservation
from h3_bot.vcmi.protocol import MAX_FRAME_BYTES, read_frame
from h3_bot.vcmi.state_store import publish

Policy = Callable[[BattleObservation], str]
logger = logging.getLogger(__name__)


def interactive(observation: BattleObservation) -> str:
    print(f"Battle {observation.battle_id}, round {observation.round}, actor {observation.active_stack_id}")
    for action in observation.legal_actions:
        print(action.model_dump_json())
    while True:
        choice = input("Action ID: ").strip()
        if choice in {action.id for action in observation.legal_actions}:
            return choice
        print("Choose an offered action ID.")


class DecisionServer(socketserver.TCPServer):
    """Sequential decisions; separate observations are isolated by IDs."""

    allow_reuse_address = True

    def __init__(self, port: int, policy: Policy | None = None, log_path: Path | None = None, state_path: Path | None = None, *, mode: str = "observe"):
        if mode not in {"observe", "control"}:
            raise ValueError("Unknown service mode")
        if mode == "control" and policy is None:
            raise ValueError("Control mode requires an external policy")
        self.latest_revisions = {}
        self.mode = mode
        self.state_path = state_path
        self.policy = policy
        self.log_path = log_path
        super().__init__(("127.0.0.1", port), DecisionHandler)


class DecisionHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection.settimeout(30)
        try:
            observation = BattleObservation.model_validate_json(read_frame(self.rfile))
            if observation.mode != self.server.mode:
                raise ValueError("Engine mode does not match service mode")
            key = (observation.battle_id, observation.viewer_side)
            previous = self.server.latest_revisions.get(key, -1)
            if observation.revision < previous or (observation.revision == previous and observation.event != "environment_error"):
                if observation.requires_action:
                    raise ValueError("Stale control decision")
                return
            self.server.latest_revisions[key] = observation.revision
            if self.server.state_path:
                publish(self.server.state_path, observation)
            reply = None
            if observation.requires_action:
                reply = ActionReply.select(observation, self.server.policy(observation))
            if self.server.log_path:
                self.server.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.server.log_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({
                        "observation": observation.model_dump(),
                        "requested_action": reply.model_dump() if reply else None,
                    }, ensure_ascii=False) + "\n")
            if reply is None:
                return
            frame = reply.model_dump_json().encode("utf-8") + b"\n"
            if len(frame) > MAX_FRAME_BYTES:
                raise ValueError("Action reply exceeds frame limit")
            self.wfile.write(frame)
        except Exception:
            # Closing the connection reports an environment error; no action fallback.
            logger.exception("Decision request failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--mode", choices=["observe", "control"], default="observe")
    parser.add_argument("--log", type=Path, default=Path("runs/battle-decisions.jsonl"))
    parser.add_argument("--state-file", type=Path, default=Path("runs/latest-battle.json"),
                        help="Publish the latest observation before policy execution")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be in range 1..65535")
    logging.basicConfig(level=logging.INFO)
    with DecisionServer(args.port, interactive if args.mode == "control" else None, args.log, args.state_file, mode=args.mode) as server:
        logger.info("Listening on 127.0.0.1:%s", server.server_address[1])
        logger.info("Mode: %s; observation events never invoke a policy", args.mode)
        if args.mode == "control":
            logger.info("Decision timeout: 30 seconds; failures halt the episode without fallback actions")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
