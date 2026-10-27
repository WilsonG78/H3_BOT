# First prototype: battle state

## Verified environment

- Debian 13, amd64.
- Debian VCMI package: `1.6.5+dfsg-2`.
- Heroes III Complete from GOG; the user confirmed that the game runs.
- The `libBattleAI.so` module is available.
- Default game data location: `~/.local/share/vcmi`.

Read-only local diagnostics: `./scripts/check-vcmi.sh`.

## Initial integration goal

Read battle state through VCMI's C++ interfaces and expose it to an external
Python application. First verify state extraction, then action execution.
An installed BattleAI module does not itself provide our state export.
The integration is a data/action adapter, not an internal decision policy.

Minimum observation fields:

- Round number and active stack.
- Stack ID, creature type, and controlling side.
- Stack count and remaining health of the wounded creature.
- Battlefield position, including all occupied hexes.
- Current attack, defense, damage, speed, and remaining shots where available.

Verify exact API calls against the selected VCMI source version. Do not assume
ABI compatibility with modules built for other releases.

## Manual baseline scenario

1. Choose a small map and a hero with a small army.
2. Approach a neutral stack and save as `battle-baseline` before attacking.
3. Start manual combat and record both armies.
4. Keep the save as a baseline for future comparisons.

Use open-field combat without spellcasting or a siege initially. Reloading a
save provides the same starting point; identical random outcomes require
separate verification.

## Next engineering tasks

1. Obtain matching VCMI sources and identify player-interface state and action hooks.
2. Define our observation and action contract independently of engine classes.
3. Confirm adapter build and loading mechanisms.
4. Export state at decision boundaries and compare it with the game UI.
5. Execute a first legal action through the adapter.

The initial adapter and state contract are implemented; see
[adapter guide](VCMI_ADAPTER.md). Runtime export from a rebuilt engine has
not yet been verified.

## Platform requirement

Target Windows, Linux, and macOS. Debian is only the verified local environment.
Use portable C++ and Python code, uv for Python, and CMake with Ninja for C++.
Compile the adapter separately for each platform against compatible VCMI builds.
The Debian diagnostic script is optional; other platforms are not yet verified.

The current integration uses the player interface, not BattleAI. See the adapter
guide for observe/control modes. Reset/step training semantics are not complete.
