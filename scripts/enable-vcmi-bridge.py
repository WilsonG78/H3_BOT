"""Install the player-interface bridge in explicitly selected VCMI 1.6.5 sources."""

import argparse
import re
from pathlib import Path

MARKER = "// H3_BOT_PLAYER_BRIDGE_V2"
BUILD_MARKER = "# H3_BOT_PLAYER_BRIDGE_V2"
LEGACY = "// H3_BOT_EXTERNAL_BRIDGE"


def inject(code: str, signature: str, statement: str) -> str:
    pattern = re.escape(signature) + r"[^\n]*\n\{"
    matches = list(re.finditer(pattern, code))
    if len(matches) != 1:
        raise ValueError(f"Unexpected player interface signature: {signature}")
    end = matches[0].end()
    return code[:end] + "\n\t" + statement + code[end:]


def enable(source: Path, project: Path) -> None:
    version = (source / "cmake_modules/VersionDefinition.cmake").read_text(encoding="utf-8")
    if not all(f"set(VCMI_VERSION_{part} {number})" in version for part, number in [("MAJOR", 1), ("MINOR", 6), ("PATCH", 5)]):
        raise ValueError("Only VCMI 1.6.5 sources are supported")
    cpp = source / "client/CPlayerInterface.cpp"
    cmake = source / "client/CMakeLists.txt"
    code, build = cpp.read_text(encoding="utf-8"), cmake.read_text(encoding="utf-8")
    legacy_cpp = source / "AI/BattleAI/BattleAI.cpp"
    legacy_cmake = source / "AI/BattleAI/CMakeLists.txt"
    old_code, old_build = legacy_cpp.read_text(encoding="utf-8"), legacy_cmake.read_text(encoding="utf-8")
    changes = {}
    if LEGACY in old_code or LEGACY in old_build:
        insertion = "\n\t" + LEGACY + "\n\tif(h3::external_battle_decision(*cb, battleID, stack)) return;"
        include = '\n#include "ExternalBattle.hpp"'
        suffix = re.search(r'\n// H3_BOT_EXTERNAL_BRIDGE\nadd_subdirectory\([^\n]+\)\ntarget_sources\(BattleAI[^\n]+\)\nset_source_files_properties\([^\n]+\)\ntarget_include_directories\(BattleAI[^\n]+\)\ntarget_link_libraries\(BattleAI PRIVATE h3_bridge\)\n?\Z', old_build)
        if old_code.count(insertion) != 1 or old_code.count(include) != 1 or not suffix:
            raise ValueError("Unrecognized legacy patch; restore/review it before migration")
        changes[legacy_cpp] = old_code.replace(insertion, "", 1).replace(include, "", 1)
        changes[legacy_cmake] = old_build[:suffix.start()]
    if MARKER in code or MARKER in build or BUILD_MARKER in build:
        if MARKER not in code or not (MARKER in build or BUILD_MARKER in build):
            raise ValueError("Partial player hook installation; review source tree")
        if MARKER in build:
            changes[cmake] = build.replace(MARKER, BUILD_MARKER)
        if not changes:
            print("Player-interface bridge is already enabled; no changes made")
            return
    else:
        if code.count('#include "CPlayerInterface.h"') != 1:
            raise ValueError("Unexpected player interface includes")
        code = code.replace('#include "CPlayerInterface.h"', '#include "CPlayerInterface.h"\n#include "ExternalBattle.hpp"\n' + MARKER, 1)
        events = [
            ("void CPlayerInterface::battleStart(", "battle_started"),
            ("void CPlayerInterface::battleNewRound(", "round_started"),
            ("void CPlayerInterface::actionFinished(", "action_finished"),
        ]
        for signature, event in events:
            code = inject(code, signature, f'h3::ExternalBattleController::observe(*cb, battleID, "{event}");')
        code = inject(code, "void CPlayerInterface::battleEnd(", 'h3::ExternalBattleController::observe(*cb, battleID, "battle_ended", static_cast<int>(br->winner));')
        # Insert after the usual event-handler guard to use the existing lock protocol.
        signature = "void CPlayerInterface::activeStack("
        pattern = re.escape(signature) + r"[^\n]*\n\{\n\tEVENT_HANDLER_CALLED_BY_CLIENT;"
        matches = list(re.finditer(pattern, code))
        if len(matches) != 1:
            raise ValueError("Unexpected activeStack lock guard")
        end = matches[0].end()
        control = '''
	if(h3::ExternalBattleController::controls())
	{
		auto unlockInterface = vstd::makeUnlockGuard(GH.interfaceMutex);
		if(h3::ExternalBattleController::decide(*cb, battleID, stack)) return;
	}
	else
		h3::ExternalBattleController::observe(*cb, battleID, "decision");'''
        code = code[:end] + control + code[end:]
        quick = "if ((replayAllowed && useQuickCombat) || forceQuickCombat)"
        if code.count(quick) != 1:
            raise ValueError("Unexpected quick-combat configuration")
        code = code.replace(quick, "if (!h3::ExternalBattleController::controls() && ((replayAllowed && useQuickCombat) || forceQuickCombat))", 1)
        adapter = (project / "adapters/vcmi").as_posix()
        build += f'''
{BUILD_MARKER}
add_subdirectory("{adapter}" "${{CMAKE_BINARY_DIR}}/h3-bridge")
target_sources(vcmiclientcommon PRIVATE "{adapter}/engine/ExternalBattle.cpp")
set_source_files_properties("{adapter}/engine/ExternalBattle.cpp" PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
target_include_directories(vcmiclientcommon PRIVATE "{adapter}/engine" "${{CMAKE_SOURCE_DIR}}")
target_link_libraries(vcmiclientcommon PRIVATE h3_bridge)
'''
        changes[cpp], changes[cmake] = code, build
    # Validate every edit before modifying any source file. Never reset a checkout.
    for path, content in changes.items():
        path.write_text(content, encoding="utf-8")
    print("Enabled player observation/control bridge; legacy BattleAI hook removed if present")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    enable(args.source.resolve(), Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    main()
