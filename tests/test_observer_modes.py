"""Observation-only traffic must never trigger policy execution or replies."""

import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from pydantic import ValidationError

from h3_bot.domain.battle.models import ActionReply, BattleObservation
from h3_bot.vcmi.server import DecisionServer
from h3_bot.vcmi.watch import load

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/battle-observer-v2.json"


class ObserverTests(unittest.TestCase):
    def test_lifecycle_contract(self):
        payload = json.loads(FIXTURE.read_text())
        for event in ["battle_started", "round_started", "action_finished", "decision"]:
            payload["event"] = event
            observation = BattleObservation.model_validate(payload)
            self.assertFalse(observation.requires_action)
            with self.assertRaises(ValueError):
                ActionReply.select(observation, "0")
        payload.update(event="battle_ended", status="terminated", winner_side=1)
        self.assertEqual(BattleObservation.model_validate(payload).winner_side, 1)
        payload.update(event="environment_error", status="error", error="Connection lost", winner_side=None)
        self.assertEqual(BattleObservation.model_validate(payload).error, "Connection lost")
        payload["error"] = None
        with self.assertRaises(ValidationError):
            BattleObservation.model_validate(payload)

    def test_control_requires_an_explicit_policy(self):
        with self.assertRaises(ValueError):
            DecisionServer(0, mode="control")

    def test_observe_service_never_invokes_a_policy_or_sends_an_action(self):
        def forbidden_policy(observation):
            self.fail("Observer invoked policy")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with DecisionServer(0, forbidden_policy, state_path=path) as server:
                thread = threading.Thread(target=server.handle_request)
                thread.start()
                with socket.create_connection(server.server_address, timeout=3) as connection:
                    connection.sendall(json.dumps(json.loads(FIXTURE.read_text())).encode() + b"\n")
                    self.assertEqual(connection.recv(1), b"")
                thread.join(timeout=3)
                self.assertEqual(load(path)[0].mode, "observe")

    def test_control_mode_lifecycle_events_do_not_invoke_policy(self):
        payload = json.loads(FIXTURE.read_text())
        payload.update(mode="control", event="battle_ended", status="terminated", winner_side=0)
        calls = []
        with DecisionServer(0, lambda obs: calls.append(obs), mode="control") as server:
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            with socket.create_connection(server.server_address, timeout=3) as connection:
                connection.sendall(json.dumps(payload).encode() + b"\n")
                self.assertEqual(connection.recv(1), b"")
            thread.join(timeout=3)
            self.assertEqual(calls, [])

    def test_out_of_order_telemetry_cannot_overwrite_newer_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with DecisionServer(0, state_path=path) as server:
                for revision in [5, 2]:
                    payload = json.loads(FIXTURE.read_text())
                    payload["revision"] = revision
                    thread = threading.Thread(target=server.handle_request)
                    thread.start()
                    with socket.create_connection(server.server_address, timeout=3) as connection:
                        connection.sendall(json.dumps(payload).encode() + b"\n")
                        self.assertEqual(connection.recv(1), b"")
                    thread.join(timeout=3)
                self.assertEqual(load(path)[0].revision, 5)

    def test_error_for_current_revision_is_published_without_policy(self):
        payload = json.loads(FIXTURE.read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with DecisionServer(0, state_path=path) as server:
                for error in [None, "Connection timed out"]:
                    if error:
                        payload.update(event="environment_error", status="error", error=error)
                    thread = threading.Thread(target=server.handle_request)
                    thread.start()
                    with socket.create_connection(server.server_address, timeout=3) as connection:
                        connection.sendall(json.dumps(payload).encode() + b"\n")
                        self.assertEqual(connection.recv(1), b"")
                    thread.join(timeout=3)
                self.assertEqual(load(path)[0].status, "error")

    @unittest.skipUnless(os.environ.get("H3_BRIDGE_PROBE"), "Native probe not configured")
    def test_cpp_send_only_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with DecisionServer(0, state_path=path) as server:
                thread = threading.Thread(target=server.handle_request)
                thread.start()
                result = subprocess.run([os.environ["H3_BRIDGE_PROBE"], str(server.server_address[1]), str(FIXTURE), "observe"], capture_output=True, text=True, timeout=5)
                thread.join(timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(load(path)[0].mode, "observe")


class SourcePatchTests(unittest.TestCase):
    def test_player_hook_is_idempotent_and_leaves_battleai_untouched(self):
        spec = importlib.util.spec_from_file_location("enable_bridge", ROOT / "scripts/enable-vcmi-bridge.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "cmake_modules/VersionDefinition.cmake": "set(VCMI_VERSION_MAJOR 1)\nset(VCMI_VERSION_MINOR 6)\nset(VCMI_VERSION_PATCH 5)\n",
                "AI/BattleAI/BattleAI.cpp": "original battle AI\n",
                "AI/BattleAI/CMakeLists.txt": "original AI build\n",
                "client/CMakeLists.txt": "add_library(vcmiclientcommon STATIC original.cpp)\n",
                "client/CPlayerInterface.cpp": '#include "CPlayerInterface.h"\n' + "\n".join(
                    f"void CPlayerInterface::{name}(args)\n{{\n\tEVENT_HANDLER_CALLED_BY_CLIENT;\n}}"
                    for name in ["battleStart", "battleNewRound", "actionFinished", "battleEnd", "activeStack"]
                ) + "\nif ((replayAllowed && useQuickCombat) || forceQuickCombat)\n{}\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            module.enable(root, ROOT)
            first = {name: (root / name).read_text() for name in files}
            module.enable(root, ROOT)
            self.assertEqual(first, {name: (root / name).read_text() for name in files})
            self.assertEqual(first["AI/BattleAI/BattleAI.cpp"], files["AI/BattleAI/BattleAI.cpp"])
            self.assertIn("ExternalBattleController::decide", first["client/CPlayerInterface.cpp"])
            self.assertIn("vcmiclientcommon PRIVATE h3_bridge", first["client/CMakeLists.txt"])
            self.assertIn("# H3_BOT_PLAYER_BRIDGE_V2", first["client/CMakeLists.txt"])
            self.assertNotIn("// H3_BOT_PLAYER_BRIDGE_V2", first["client/CMakeLists.txt"])


if __name__ == "__main__":
    unittest.main()
