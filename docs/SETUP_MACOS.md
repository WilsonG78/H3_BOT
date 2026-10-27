# macOS setup from scratch

Target: Apple Silicon (arm64) or Intel (x86_64), using native Apple Clang and
Ninja. This project has not yet executed the full build on either Mac platform.
The procedure follows upstream's Homebrew approach, with a pinned Boost build
to avoid silently selecting an incompatible new Boost release.

Homebrew's current SDL2 offering is `sdl2-compat` (SDL2 API implemented on SDL3).
The original VCMI 1.6.5 guide used native SDL2. This combination needs explicit
runtime validation; do not treat the guide as a tested macOS binary release.
If a new macOS/compiler or Homebrew revision exposes another incompatibility,
record it and stop rather than replacing VCMI with `develop` on one machine.

## 1. Install developer tools and Homebrew

Install Apple's tools:

```bash
xcode-select --install
```

Complete the installer. Install [Homebrew](https://brew.sh/) using its official
instructions and follow the printed shell PATH setup. Then:

```bash
brew install git cmake ninja uv pkgconf sdl2-compat sdl2_image sdl2_mixer sdl2_ttf tbb innoextract
xcrun --find clang
cmake --version
ninja --version
uv --version
uname -m
brew --prefix
```

CMake must be >= 3.21. On Apple Silicon, use a native arm64 terminal and native
Homebrew, normally under `/opt/homebrew`; avoid a Rosetta x86_64 terminal. Intel
Homebrew normally uses `/usr/local`. Do not mix architectures or copy native
libraries from another Mac. Some Homebrew bottles are only available on newer
supported macOS versions; older systems may need source builds.

Game movies are disabled in this first setup, so FFmpeg is not needed. The Qt
launcher/editor are not built either.

## 2. Clone the project and pinned engine

Choose a writable folder without spaces for the development tree:

```bash
mkdir -p "$HOME/Developer"
cd "$HOME/Developer"
git clone https://github.com/WilsonG78/H3_BOT.git
cd H3_BOT
uv python install 3.12
uv sync --locked
uv run h3-battle-watch --file data/fixtures/battle-observer-v2.json --once
mkdir -p work
git clone --branch 1.6.5 --depth 1 --recurse-submodules https://github.com/vcmi/vcmi.git work/vcmi-1.6.5
```

Keep subsequent commands at the repository root unless a block explicitly
changes directory. `--recurse-submodules` is required for bundled FuzzyLite.

## 3. Build a private Boost 1.83 dependency

Current unversioned Homebrew Boost is newer than the version validated in our
Linux build. The older Homebrew `boost@1.85` formula is disabled, so do not rely
on `brew install boost@1.85` working. Build the needed 1.83 components locally.
This does not overwrite a Homebrew Boost used by another application.

```bash
Repo="$PWD"
curl -fL https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2 -o work/boost_1_83_0.tar.bz2
printf '%s  %s\n' '6478edfe2f3305127cffe8caf73ea0176c53769f4bf1585be237eb30798c3b8e' 'work/boost_1_83_0.tar.bz2' | shasum -a 256 -c -
tar -xjf work/boost_1_83_0.tar.bz2 -C work
cd work/boost_1_83_0
./bootstrap.sh --prefix="$Repo/work/boost-install" --with-libraries=date_time,filesystem,locale,program_options,system,thread
./b2 -j2 install variant=release link=shared threading=multi cxxstd=17
cd "$Repo"
```

Do not continue if checksum verification or compilation fails. The checksum is
from the [official archive metadata](https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2.json).
Boost 1.83 is the selected compatibility baseline; this macOS compilation itself
is still unverified. Building all dependencies is not instantaneous and needs
several GB of free disk space.

## 4. Apply our adapter and compatibility patch

```bash
uv run python scripts/enable-vcmi-bridge.py --source work/vcmi-1.6.5
git -C work/vcmi-1.6.5 apply ../../patches/vcmi-1.6.5-sdl-mixer.patch
```

Apply the patch once to a fresh source tree. The hook script can be rerun and
will report that an existing installation is already enabled. Do not move the
H3 Bot repository after patching without reviewing the generated CMake paths.

## 5. Configure and compile

```bash
Repo="$PWD"
cmake -S work/vcmi-1.6.5 -B work/vcmi-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  "-DBOOST_ROOT=$Repo/work/boost-install" \
  -DBoost_NO_SYSTEM_PATHS=ON -DBoost_NO_BOOST_CMAKE=ON \
  "-DCMAKE_PREFIX_PATH=$Repo/work/boost-install;$(brew --prefix);$(brew --prefix sdl2-compat)" \
  -DENABLE_LAUNCHER=OFF -DENABLE_EDITOR=OFF \
  -DENABLE_TRANSLATIONS=OFF -DENABLE_TEST=OFF \
  -DENABLE_VIDEO=OFF -DFORCE_BUNDLED_FL=ON \
  -DENABLE_MONOLITHIC_INSTALL=ON
cmake --build work/vcmi-build --parallel 2
```

Check the configure output: Boost must resolve to `work/boost-install`, SDL must
resolve to the same Homebrew architecture as the compiler, and the output must
include the H3 bridge. `CMAKE_POLICY_VERSION_MINIMUM` allows bundled older CMake
projects to configure with CMake 4; it may be unused on earlier CMake versions.
If configuration fails, do not continue with an old cache. Use a fresh build
directory after changing architecture/compiler/dependency strategy.

Keep the build directory. The intended development output is:

```text
work/vcmi-build/bin/vcmiclient
work/vcmi-build/bin/vcmiserver
work/vcmi-build/bin/AI/
work/vcmi-build/bin/config
work/vcmi-build/bin/Mods
```

This is a command-line development build, not a signed `.app` or distributable
DMG. Startup smoke test from the repository root:

```bash
uv run python scripts/run-vcmi.py --mode off -- --version
```

If the loader reports a missing `.dylib`, inspect
`otool -L work/vcmi-build/bin/vcmiclient`. Keep the selected Boost installation
and Homebrew packages in place; do not mix libraries from another architecture.
A successful `--version` does not prove rendering or battle callbacks work.

## 6. Prepare original Heroes III data

Download both GOG offline installer files into the same folder. You can use an
official [VCMI launcher for your Mac architecture](https://github.com/vcmi/vcmi/releases/tag/1.6.5)
to import them, or extract with innoextract. For example, replace the installer
path below with your actual `.exe` filename:

```bash
innoextract --output-dir work/h3-extracted "/absolute/path/to/your-gog-installer.exe"
mkdir -p "$HOME/Library/Application Support/vcmi"
find work/h3-extracted -type d -iname Data
```

Find the extracted folder containing `Data`, `Maps`, and `Mp3` (it may be under
`app/` depending on the installer). In Finder, use **Go → Go to Folder** and open
`~/Library/Application Support/vcmi/`. Copy those three directories into it,
preserving their names and contents. Do not copy only the installer or the
extra parent `app` directory. Keep the original files outside Git.

## 7. Start the three processes

Open three terminals at `~/Developer/H3_BOT`.

Terminal 1:

```bash
uv run h3-battle-server --mode observe
```

Terminal 2:

```bash
uv run h3-battle-watch
```

Terminal 3:

```bash
uv run python scripts/run-vcmi.py --mode observe
```

Start a map and enter manual combat with quick/auto combat disabled. Snapshots
should appear in the inspector with fresh timestamps and actual engine data.
Record the result of this first macOS validation rather than assuming the
synthetic fixture or `--version` confirms gameplay.

## Rebuild and troubleshooting

- C++ changes: `cmake --build work/vcmi-build --parallel 2`, then restart the game.
- Python changes: restart the Python process only.
- Missing `xcrun` compiler: check the Xcode/CLT selection with `xcode-select -p`.
- `Bad CPU type` or incompatible architecture: check `uname -m`, `brew --prefix`,
  and `file work/vcmi-build/bin/vcmiclient`; rebuild consistently for one CPU.
- Missing `config`/`Mods`: use our launcher script, which sets the build's `bin/`
  as the working directory; keep upstream asset-copy behavior enabled.
- Homebrew SDL3/SDL2 compatibility or compiler errors: preserve the first error
  and dependency versions for a platform fix. Do not switch to new VCMI sources
  without also updating/testing the adapter API.

Sources: [VCMI 1.6.5 macOS build guide](https://github.com/vcmi/vcmi/blob/1.6.5/docs/developers/Building_macOS.md),
[SDL2 compatibility formula](https://formulae.brew.sh/formula/sdl2-compat),
[Boost source archive](https://archives.boost.io/release/1.83.0/source/).
See [shared setup](SETUP.md) and [adapter limitations](VCMI_ADAPTER.md).
