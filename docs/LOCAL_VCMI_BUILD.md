# Local Linux VCMI build

This machine uses an isolated build under the repository's ignored `work/`
directory. No system package was installed or replaced to prepare it.

## Locations

- Sources: `work/vcmi-1.6.5` (upstream release with our player-interface hook).
- Build tree: `work/vcmi-build`.
- Client: `work/vcmi-build/bin/vcmiclient` after a successful build.
- Server: `work/vcmi-build/bin/vcmiserver` after a successful build.
- Downloaded Debian packages: `work/vcmi-debs`.
- Extracted build SDK: `work/vcmi-sdk`.
- Initial compilation log: `work/vcmi-build/build.log`.

Dependencies were downloaded with apt's download-only mode and extracted with
`dpkg-deb -x`. Some SDK libraries reference compatible runtime libraries already
installed on this machine. This local SDK is not a portable distribution.
Python dependency management remains uv; C++ builds use CMake and Ninja.

The build uses GCC 14 and Release mode with `-O1 -DNDEBUG`. The client, dedicated
server, and ordinary game AI modules are needed for normal game operation.
The launcher, editor, translations, and upstream tests are disabled. The
external bridge does not use the bundled AI to select its controlled actions;
those modules remain available for ordinary opponents and adventure-map play.

## Start observation

Run all commands from the repository root, in separate terminals:

```bash
uv run h3-battle-server --mode observe
```

```bash
uv run h3-battle-watch
```

```bash
uv run python scripts/run-vcmi.py --mode observe
```

The launcher script changes to the build's `bin/` directory so that VCMI finds
its matching configuration, assets, server, and AI libraries. It sets the local
SDK library path and bridge environment without altering system packages.
Original game data is read from the existing VCMI user installation. Use a
manual battle with auto/quick combat disabled to inspect your actions.

For custom external control, use `--mode control` on both server and game
launcher. The CLI server is interactive; a custom RL policy should use the
Python server API. See [adapter guide](VCMI_ADAPTER.md) for limitations.

## Rebuild

```bash
uv run python scripts/rebuild-vcmi.py --jobs 2
```

This uses CMake on PATH or the configured build's cached executable. If temporary
build tools have been removed, install CMake >= 3.21 and Ninja and reconfigure
with the available executables. Two compiler processes limit memory pressure.

To configure another machine, follow VCMI 1.6.5's platform build instructions
and apply `scripts/enable-vcmi-bridge.py`. Do not copy this machine's SDK or assume
these Linux paths apply to Windows/macOS. The source adapter and protocol remain
cross-platform; other platform builds are not verified yet.

## Compatibility adjustment

The local source has `patches/vcmi-1.6.5-sdl-mixer.patch` applied to handle
Debian 13's SDL_mixer type declaration. The source-integration script also
uses CMake `#` comments in generated build entries. These fixes were discovered
during the full build; they do not change game rules or policy decisions.

## Verification result

The complete client, server, and five AI modules build successfully. The client
reports VCMI 1.6.5 with `--version`; all runtime libraries resolve, and its symbol
table contains `ExternalBattleController::observe` and `::decide`. A real battle
with observation capture still requires manual verification.

For the isolated SDK, the architecture-specific SDL configuration header is
linked into `usr/include/SDL2/` so targets without an explicit multiarch include
path can resolve it. System installations do not need this SDK-only adjustment.
