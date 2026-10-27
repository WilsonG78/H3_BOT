"""Offline contract checks and optional real C++/Python transport tests."""

import copy
import io
import json
import os
import socket
import socketserver
import subprocess
import threading
import unittest
from pathlib import Path

from pydantic import ValidationError

from h3_bot.domain.battle.models import ActionReply, BattleObservation
from h3_bot.vcmi.protocol import MAX_FRAME_BYTES, read_frame
from h3_bot.vcmi.server import DecisionServer

def defend(observation):
    return next(action.id for action in observation.legal_actions if action.type == "defend")


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/battle-observation-v2.json"
PROBE = os.environ.get("H3_BRIDGE_PROBE")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())

    def test_fixture_and_reply(self):
        obs = BattleObservation.model_validate(self.payload)
        reply = ActionReply.select(obs, "0")
        self.assertEqual(reply.revision, obs.revision)
        with self.assertRaises(ValueError):
            ActionReply.select(obs, "unknown")

    def test_dangling_actor_and_targets_are_rejected(self):
        self.payload["active_stack_id"] = 999
        with self.assertRaises(ValidationError):
            BattleObservation.model_validate(self.payload)
        self.payload["active_stack_id"] = 1
        self.payload["legal_actions"].append(dict(id="4", type="shoot", actor_stack_id=1, target_stack_id=999))
        with self.assertRaises(ValidationError):
            BattleObservation.model_validate(self.payload)

    def test_duplicate_ids_and_unsupported_schema_are_rejected(self):
        for field in ["stacks", "legal_actions"]:
            payload = copy.deepcopy(self.payload)
            payload[field].append(payload[field][0])
            with self.assertRaises(ValidationError):
                BattleObservation.model_validate(payload)
        self.payload["schema_version"] = 99
        with self.assertRaises(ValidationError):
            BattleObservation.model_validate(self.payload)

    def test_truncated_and_oversized_frames(self):
        for frame in [b"", b"{}", b"x" * MAX_FRAME_BYTES + b"\n"]:
            with self.assertRaises(ValueError):
                read_frame(io.BytesIO(frame))

    def test_python_service_round_trip(self):
        with DecisionServer(0, defend, mode="control") as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            with socket.create_connection(server.server_address, timeout=3) as connection:
                connection.sendall(FIXTURE.read_bytes().replace(b"\n", b"") + b"\n")
                with connection.makefile("rb") as stream:
                    reply = ActionReply.model_validate_json(read_frame(stream))
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(reply.action_id, "0")


@unittest.skipUnless(PROBE, "Set H3_BRIDGE_PROBE to the compiled C++ probe")
class NativeBridgeTests(unittest.TestCase):
    def probe(self, port):
        return subprocess.run([PROBE, str(port), str(FIXTURE)], capture_output=True, text=True, timeout=5)

    def test_cpp_observation_to_python_and_action_back(self):
        with DecisionServer(0, defend, mode="control") as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            result = self.probe(server.server_address[1])
            thread.join(timeout=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["type"], "defend")

    def test_cpp_rejects_stale_unknown_and_malformed_replies(self):
        for change in [{"revision": 99}, {"action_id": "unknown"}, {"type": "observation"}, {"schema_version": 99}]:
            with self.subTest(change=change):
                class Handler(socketserver.StreamRequestHandler):
                    def handle(inner):
                        obs = BattleObservation.model_validate_json(read_frame(inner.rfile))
                        reply = ActionReply.select(obs, "0").model_dump()
                        reply.update(change)
                        frame = json.dumps(reply).encode() + b"\n"
                        # Split writes exercise stream framing instead of message-sized recv assumptions.
                        inner.wfile.write(frame[:4])
                        inner.wfile.flush()
                        inner.wfile.write(frame[4:])

                with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
                    thread = threading.Thread(target=server.handle_request)
                    thread.start()
                    result = self.probe(server.server_address[1])
                    thread.join(timeout=3)
                    self.assertEqual(result.returncode, 1, result.stdout)

    def test_cpp_reports_disconnect(self):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(4096)

        with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            result = self.probe(server.server_address[1])
            thread.join(timeout=3)
            self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
