# Windows setup from scratch

Target: Windows 10/11 x64 with MSVC v143. Native Windows ARM64 is not covered.
This procedure has not yet been run on Windows by this project.

## 1. Install tools

Install:

- [Git for Windows](https://git-scm.com/downloads/win).
- [Visual Studio 2022 Build Tools](https://visualstudio.microsoft.com/downloads/),
  including **Desktop development with C++**, MSVC v143 x64/x86, and a Windows SDK.
  Include the C++ CMake tools workload component, which provides CMake/Ninja.
- [CMake](https://cmake.org/download/) >= 3.21 if not available with those tools.
- [Ninja](https://github.com/ninja-build/ninja/releases) if not already available.
- [7-Zip](https://www.7-zip.org/).
- [uv](https://docs.astral.sh/uv/getting-started/installation/), for example:

  ```powershell
  winget install --id astral-sh.uv --exact
  ```

Open **Developer PowerShell for VS 2022** targeting x64 (use the x64 Native Tools
prompt/developer-shell configuration if necessary). Reopen it after installing
new PATH entries. All following commands use PowerShell, not cmd.exe.

```powershell
git --version
uv --version
cmake --version
ninja --version
cl
```

`cl` should identify an x64 compiler. Choose a short, writable ASCII-only path
such as `C:\dev\H3_BOT`; avoid Program Files and cloud-synced build directories.

## 2. Clone H3 Bot and VCMI

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
Set-Location C:\dev
git clone https://github.com/WilsonG78/H3_BOT.git
Set-Location H3_BOT
uv python install 3.12
uv sync --locked
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --once
New-Item -ItemType Directory -Force work | Out-Null
git clone --branch 1.6.5 --depth 1 --recurse-submodules https://github.com/vcmi/vcmi.git work/vcmi-1.6.5
```

You should now be at the repository root. Do not clone over an existing local
source tree. If the team provided the repository another way, open its root
instead of cloning a second copy.

## 3. Download the matching Windows dependencies

Use the official [VCMI Windows dependency release v1.6](https://github.com/vcmi/vcmi-deps-windows/releases/tag/v1.6).
Download **`vcpkg-export-x64-windows-v143.7z`**, not the `-dbg` archive and not an
x86 package. This is the bundle recommended by the upstream 1.6.5 Windows guide.

```powershell
Invoke-WebRequest -Uri "https://github.com/vcmi/vcmi-deps-windows/releases/download/v1.6/vcpkg-export-x64-windows-v143.7z" -OutFile "work/vcmi-deps-x64.7z"
& "$env:ProgramFiles\7-Zip\7z.exe" x "work/vcmi-deps-x64.7z" "-owork"
Test-Path work/vcpkg/scripts/buildsystems/vcpkg.cmake
Test-Path work/vcpkg/installed/x64-windows/bin
```

Both checks must return `True`. The archive should contain a `vcpkg` directory.
If its layout differs, move that directory under `work` or adapt the toolchain
path below. This is a prebuilt export; do not run bootstrap/update against it.
Use release libraries with the Release configuration.

## 4. Apply the H3 Bot hook and compatibility fix

```powershell
uv run python scripts/enable-vcmi-bridge.py --source work/vcmi-1.6.5
git -C work/vcmi-1.6.5 apply ../../patches/vcmi-1.6.5-sdl-mixer.patch
```

Apply the compatibility patch once to a fresh checkout. It uses SDL_mixer's own
type declaration instead of hard-coding an internal struct name. If it reports
an already-applied or mismatched patch, inspect the source rather than forcing it.
The hook script is idempotent and modifies the player interface, not BattleAI.

## 5. Configure and build with Ninja

```powershell
$Repo = (Get-Location).Path
$Toolchain = Join-Path $Repo "work/vcpkg/scripts/buildsystems/vcpkg.cmake"
cmake -S work/vcmi-1.6.5 -B work/vcmi-build -G Ninja `
  "-DCMAKE_TOOLCHAIN_FILE=$Toolchain" `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -DCMAKE_BUILD_TYPE=Release `
  -DENABLE_LAUNCHER=OFF -DENABLE_EDITOR=OFF `
  -DENABLE_TRANSLATIONS=OFF -DENABLE_TEST=OFF `
  -DENABLE_VIDEO=OFF -DFORCE_BUNDLED_FL=OFF
cmake --build work/vcmi-build --parallel 2
```

Stop if configuration fails; do not continue with a stale build. `ENABLE_VIDEO`
is disabled to avoid unnecessary FFmpeg integration in this first bridge build;
this disables game movies, not battle rendering. Qt-based launcher/editor are
also omitted. CMake downloads the bridge's pinned JSON dependency automatically.

The expected client is `work/vcmi-build/bin/VCMI_client.exe`, with a matching
`VCMI_server.exe` and AI libraries. Ensure the exported dependency DLL directory
is available in the launch terminal:

```powershell
$env:PATH = "$Repo\work\vcpkg\installed\x64-windows\bin;$env:PATH"
uv run python scripts/run-vcmi.py --mode off -- --version
```

If VCMI's post-build copy step cannot find `AI/fuzzylite.dll` or `AI/tbb12.dll`,
inspect the export for those DLLs and place the matching release files in
`work/vcmi-build/bin/AI`, then rerun the build. Do not mix DLLs from a different
VCMI release or download individual DLLs from unrelated sites.

## 6. Install the original game data

Download the GOG offline installer (`.exe` and matching `.bin` together) from
your account and install Heroes III Complete. Copy its extracted `Data`, `Maps`,
and `Mp3` directories to the VCMI user data folder:

```powershell
$VcmiData = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\vcmi'
New-Item -ItemType Directory -Force $VcmiData | Out-Null
Write-Output $VcmiData
```

Use Explorer to copy the three directories into the printed path, preserving
their contents. Alternatively use the official [VCMI 1.6.5 launcher](https://github.com/vcmi/vcmi/releases/tag/1.6.5)
to import the GOG installer. The launcher helps prepare data; use our rebuilt
client for bridge gameplay.

## 7. Run manual observation

Open three terminals at `C:\dev\H3_BOT`.

Terminal 1:

```powershell
uv run h3-battle-server --mode observe
```

Terminal 2:

```powershell
uv run h3-battle-watch
```

Terminal 3 (Developer PowerShell with dependency DLLs on PATH):

```powershell
$env:PATH = "$PWD\work\vcpkg\installed\x64-windows\bin;$env:PATH"
uv run python scripts/run-vcmi.py --mode observe
```

Start a map and a manual battle with quick/auto combat disabled. Watch for
actual events, stack IDs, counts, and positions. The inspector may display an
older snapshot until the first new event; check the timestamp.

## Rebuild and troubleshooting

- After C++ changes: `cmake --build work/vcmi-build --parallel 2`, then restart.
- Python-only changes: restart the Python process; no native compilation needed.
- Compiler missing/wrong architecture: reopen an x64 developer shell.
- Ninja toolchain error: remove no files blindly; use a new build directory if
  switching from a Visual Studio generator or from x86 to x64.
- Missing DLL: check the release bundle's `bin` on PATH in the SAME terminal
  launching the game. Build output and official installed binaries are separate.
- No observations: verify both processes use observe mode, you launched the
  rebuilt executable, and a manual battle actually started.

Source: [upstream VCMI 1.6.5 Windows build guide](https://github.com/vcmi/vcmi/blob/1.6.5/docs/developers/Building_Windows.md).
See [shared setup](SETUP.md) and [adapter limitations](VCMI_ADAPTER.md).
