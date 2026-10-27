"""Inspector behavior and observation publication timing."""

import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from h3_bot.domain.battle.models import BattleObservation
from h3_bot.vcmi.protocol import read_frame
from h3_bot.vcmi.server import DecisionServer

def defend(observation):
    return next(action.id for action in observation.legal_actions if action.type == "defend")

from h3_bot.vcmi.state_store import publish
from h3_bot.vcmi.watch import load, render

FIXTURE = Path(__file__).resolve().parents[1] / "data/fixtures/battle-observation-v2.json"


class WatchTests(unittest.TestCase):
    def test_fixture_render_and_snapshot_replacement(self):
        observation, received = load(FIXTURE)
        self.assertIsNone(received)
        output = render(observation, received)
        for text in ["synthetic", "core:pikeman", "100", "A1", "D2", "OFFERED ACTIONS"]:
            self.assertIn(text, output)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/latest.json"
            publish(path, observation)
            mapped, timestamp = load(path)
            self.assertEqual(mapped, observation)
            self.assertIsNotNone(timestamp.tzinfo)
            updated = observation.model_copy(update={"revision": 2})
            publish(path, updated)
            self.assertEqual(load(path)[0].revision, 2)
            self.assertEqual([item.name for item in path.parent.iterdir()], ["latest.json"])

    def test_dead_stack_does_not_occupy_board_cell(self):
        observation, _ = load(FIXTURE)
        observation.stacks[1].alive = False
        self.assertNotIn("D2", render(observation, None))

    def test_invalid_observation_is_not_presented_as_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"observation": {}, "received_at": "invalid"}')
            with self.assertRaises(ValueError):
                load(path)

    def test_state_is_published_before_policy_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            observed = []

            def policy(observation):
                observed.append(load(path)[0] == observation)
                return defend(observation)

            with DecisionServer(0, policy, state_path=path, mode="control") as server:
                thread = threading.Thread(target=server.handle_request)
                thread.start()
                with socket.create_connection(server.server_address, timeout=3) as connection:
                    connection.sendall(json.dumps(json.loads(FIXTURE.read_text())).encode() + b"\n")
                    with connection.makefile("rb") as stream:
                        reply = json.loads(read_frame(stream))
                thread.join(timeout=3)
                self.assertEqual(observed, [True])
                self.assertEqual(reply["action_id"], "0")


if __name__ == "__main__":
    unittest.main()
