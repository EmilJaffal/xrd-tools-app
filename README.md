# XRD Tools

A standalone desktop app combining two tools as tabs of one window:

- **XRD Match** (`xrd_match/`) — ported from [xrd-match-web-GUI](https://github.com/EmilJaffal/xrd-match-web-GUI): CIF/`.xy` overlay comparison, lattice-parameter tuning, and Pawley/Rietveld `.inp` generation for TOPAS.
- **MultiPattern XRD** (`multipattern_xrd/`) — ported from [XRD-Tool-GUI](https://github.com/EmilJaffal/XRD-Tool-GUI): compare multiple `.xy` patterns at once.

Both are still ordinary Dash apps under the hood; `app_factory.py` mounts them as two tabs of a single Dash instance, and `desktop_main.py` wraps that in a native window via [pywebview](https://pywebview.flowrl.com/) instead of a browser tab.

## Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/EmilJaffal/xrd-tools-app.git
cd xrd-tools-app

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run it (no packaging needed)

```bash
python desktop_main.py            # opens a native window
# or, for a plain browser tab instead:
python app_factory.py              # then open http://127.0.0.1:8050
```

## Build a standalone app

**macOS** (works on this machine):
```bash
./build/build_mac.sh
open "dist/XRD Tools.app"
```

**Windows** — PyInstaller can't cross-compile, so this must run *on* a Windows machine (or via the included GitHub Actions workflow, `.github/workflows/build-windows.yml`, triggered manually once this repo has a remote):
```bat
build\build_windows.bat
dist\"XRD Tools"\"XRD Tools.exe"
```

## Layout

```
xrd_match/            XRD Match tab: create_layout() / register_callbacks(app)
multipattern_xrd/      MultiPattern XRD tab: create_layout(app) / register_callbacks(app)
app_factory.py         builds the one Dash() instance, mounts both tabs
desktop_main.py         pywebview entrypoint (native window)
assets/                CSS scoped per tab (.tab-xrd-match / .tab-multipattern) + shared fonts
build/                 PyInstaller spec + build scripts (mac tested, windows scripted)
```

## Notes

- Each tab's assets are CSS-scoped under `.tab-xrd-match` / `.tab-multipattern` so one tab's font rules can't bleed into the other (both tabs' assets load into the same page).
- `xrd_match/callbacks.py`'s Pawley/Riet `.inp` generators no longer also write to the current working directory (unlike the original web app) — inside a packaged desktop app, cwd may not be writable; the content is delivered entirely through `dcc.Download`.
- Not carried over from the source repos: `make_riet_inps.py` (personal hardcoded paths, unused by the app) and a few dead/duplicate component definitions.

## Troubleshooting

- **macOS build fails to code-sign** with `resource fork, Finder information, or similar detritus not allowed`: this happens when the project folder lives somewhere Finder/iCloud tags with extra metadata (e.g. under an iCloud-synced Desktop). Fix by re-signing after the build:
  ```bash
  xattr -cr "dist/XRD Tools.app"
  codesign -s - --force --deep "dist/XRD Tools.app"
  ```
- **`.cif`/`.xy` upload buttons don't filter file types in the native window**: the macOS open panel can only grey out files it recognizes by a registered type, and `.cif`/`.xy` aren't standard system types — `build/xrd_tools.spec` registers them as custom UTIs, but a fresh build may need Launch Services to pick that up:
  ```bash
  /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "dist/XRD Tools.app"
  ```
  Regardless of what the picker shows, uploading the wrong file type is always rejected with an on-screen error — this only affects how much the OS dialog itself grays out.

## License

[MIT](LICENSE)
