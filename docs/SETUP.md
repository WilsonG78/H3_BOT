# Setup from a fresh clone

## Choose your platform

- [Windows 10/11 x64: MSVC + Ninja + official dependency bundle](SETUP_WINDOWS.md)
- [macOS: Apple Silicon or Intel, Apple Clang + Ninja](SETUP_MACOS.md)
- [Debian 13 / Linux](SETUP_LINUX.md)

These guides build **VCMI 1.6.5 with the H3 Bot adapter**. Downloading an ordinary
VCMI installer is useful for importing game data, but that executable cannot
send our bridge observations. There are no ready-made H3 Bot engine packages.
Each developer currently builds once for their own OS/architecture.

The Linux build is verified locally through compilation and `--version` startup.
The Windows and macOS guides are derived from upstream 1.6.5 build instructions
and source inspection, but have NOT been executed on those systems. In
particular, today's Homebrew libraries differ from the original release's
dependencies. Treat those builds as first-platform validation, not tested releases.

## Where to download things

- H3 Bot: <https://github.com/WilsonG78/H3_BOT>
- VCMI release and optional game-data-import launcher:
  <https://github.com/vcmi/vcmi/releases/tag/1.6.5>
- VCMI source repository: <https://github.com/vcmi/vcmi>
- Heroes III Complete: your own GOG offline installer or existing installation.
  <https://www.gog.com/en/game/heroes_of_might_and_magic_3_complete_edition>
- Python environment manager: <https://docs.astral.sh/uv/getting-started/installation/>

Use the tag `1.6.5`, not `develop` or the latest VCMI release: our patcher checks
the source version and the adapter uses that API. Clone recursively so the
bundled FuzzyLite dependency is available. Do not copy the original developer's
Linux SDK, `.venv`, build outputs, or native libraries to another OS.

## Original Heroes III data

You need the Windows data from Complete or Shadow of Death, regardless of the
host OS. The Steam HD Edition alone is not a replacement for these files.
Keep the GOG `.exe` and its matching `.bin` file together. Import with an official
VCMI launcher, install the game on Windows, or extract the offline installer with
innoextract. Copy the actual `Data`, `Maps`, and `Mp3` directories to:

| OS | Game data directory |
| --- | --- |
| Windows | The Windows Documents known folder, then `My Games\vcmi` |
| macOS | `~/Library/Application Support/vcmi/` |
| Linux | `${XDG_DATA_HOME:-$HOME/.local/share}/vcmi/` |

The Windows Documents folder may be redirected to OneDrive. The Windows guide
uses the OS known-folder API instead of assuming `%USERPROFILE%\Documents`.
Do not copy only the GOG installer files into these directories: the engine
needs their extracted contents. Keep assets, saves, installers, and credentials
outside version control.

## Expected result

1. `uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --once`
   works without a game and identifies its data as synthetic.
2. The custom client starts with `--version` and reports VCMI 1.6.5.
3. Run the receiver and inspector from the repository root:

   ```bash
   uv run h3-battle-server --mode observe
   ```

   ```bash
   uv run h3-battle-watch
   ```

4. Launch the rebuilt game with the matching mode, enter a manual battle, and
   leave quick/auto combat disabled. The inspector should receive actual events.

Compilation and `--version` are not proof of battle integration. Record the
first real battle observation, source commit, compiler, OS, architecture, and
dependency versions when validating a new platform.

For model control, use `--mode control` on the receiver and game launcher.
The CLI asks for action IDs; your RL policy will supply those through the Python
API. The adapter itself contains no strategy or fallback action. Automatic
training/reset and the adventure-map bridge are not implemented.

## Updating

Python-only changes need a process restart, not an engine rebuild. After C++
changes, rebuild incrementally and restart the game. Keep existing build output
to reuse compiled files. Do not change generator, compiler, architecture, or
VCMI version inside an existing build tree: use a different build directory.

See [adapter details](VCMI_ADAPTER.md) and [inspector usage](BATTLE_INSPECTOR.md).
