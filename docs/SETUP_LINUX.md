# Debian 13 setup from scratch

This is a conventional system-dependency route for a new Debian 13 machine.
The original development machine used an isolated downloaded SDK instead; that
prepared setup and launch commands are in [local build notes](LOCAL_VCMI_BUILD.md).
Other Linux distributions need their equivalent development packages.

## 1. Tools and dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and:

```bash
sudo apt update
sudo apt install git cmake ninja-build g++ pkgconf zlib1g-dev \
  libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  libboost-filesystem-dev libboost-system-dev libboost-thread-dev \
  libboost-program-options-dev libboost-locale-dev libboost-date-time-dev \
  libtbb-dev libfuzzylite-dev innoextract
```

Game movies, launcher/editor, and upstream tests are disabled below, so FFmpeg
and Qt development dependencies are unnecessary for this minimal bridge setup.
Use CMake >= 3.21. Commands below start from a writable development directory.

## 2. Sources and Python environment

```bash
git clone https://github.com/WilsonG78/H3_BOT.git
cd H3_BOT
uv python install 3.12
uv sync --locked
mkdir -p work
git clone --branch 1.6.5 --depth 1 --recurse-submodules https://github.com/vcmi/vcmi.git work/vcmi-1.6.5
uv run python scripts/enable-vcmi-bridge.py --source work/vcmi-1.6.5
git -C work/vcmi-1.6.5 apply ../../patches/vcmi-1.6.5-sdl-mixer.patch
```

Use a fresh checkout; do not apply the compatibility patch twice. If reusing the
prepared local build, skip source cloning/patching and follow its build notes.

## 3. Configure and build

```bash
cmake -S work/vcmi-1.6.5 -B work/vcmi-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_LAUNCHER=OFF -DENABLE_EDITOR=OFF \
  -DENABLE_TRANSLATIONS=OFF -DENABLE_TEST=OFF \
  -DENABLE_VIDEO=OFF -DFORCE_BUNDLED_FL=OFF \
  -DENABLE_MONOLITHIC_INSTALL=ON
cmake --build work/vcmi-build --parallel 2
uv run python scripts/run-vcmi.py --mode off -- --version
```

The rebuilt client is `work/vcmi-build/bin/vcmiclient`. The root project's
`cmake --preset debug` builds only the standalone transport, not this full engine.

## 4. Import Heroes III data

Use the official VCMI launcher, an existing game installation, or innoextract.
Keep the GOG `.exe` and `.bin` together. Replace the path below with your installer:

```bash
innoextract --output-dir work/h3-extracted "/absolute/path/to/your-gog-installer.exe"
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/vcmi"
find work/h3-extracted -type d -iname Data
```

Copy extracted `Data`, `Maps`, and `Mp3` directly into that `vcmi` directory.
The parent extraction folder may be `app/`; locate it before copying. Assets and
saves must remain outside Git.

## 5. Run

From the repository root in three separate terminals:

```bash
uv run h3-battle-server --mode observe
```

```bash
uv run h3-battle-watch
```

```bash
uv run python scripts/run-vcmi.py --mode observe
```

Enter a manual battle with quick/auto combat disabled. Confirm that actual
observations arrive, not just the synthetic offline example. Full gameplay still
needs verification even though the local build and startup checks passed.

After C++ edits, run `cmake --build work/vcmi-build --parallel 2`. Python changes
do not require native compilation. For errors, see the
[adapter guide](VCMI_ADAPTER.md). Upstream reference:
[VCMI 1.6.5 Linux build guide](https://github.com/vcmi/vcmi/blob/1.6.5/docs/developers/Building_Linux.md).
