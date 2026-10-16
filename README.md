# XRD Tools

A standalone desktop app combining two tools as tabs of one window:

- **XRD Match** (`xrd_match/`) — ported from [xrd-match-web-GUI](https://github.com/EmilJaffal/xrd-match-web-GUI): CIF/`.xy` overlay comparison, lattice-parameter tuning, and Pawley/Rietveld `.inp` generation for TOPAS.
- **MultiPattern XRD** (`multipattern_xrd/`) — ported from [XRD-Tool-GUI](https://github.com/EmilJaffal/XRD-Tool-GUI): compare multiple `.xy` patterns at once.

Both are still ordinary Dash apps under the hood; `app_factory.py` mounts them as two tabs of a single Dash instance, and `desktop_main.py` wraps that in a native window via [pywebview](https://pywebview.flowrl.com/) instead of a browser tab.

## Download and run (no Python needed)

Grab the build for your platform from the [latest release](https://github.com/EmilJaffal/xrd-tools-app/releases/latest):

- **macOS** (Apple Silicon only): `xrd-tools-mac.dmg` → open it, drag **XRD Tools** into Applications, then launch it from there or Spotlight.
- **Windows**: `xrd-tools-windows.zip` → extract it anywhere, then run `XRD Tools.exe` inside the extracted folder.

**First-launch warnings are expected** — the builds aren't signed with a paid developer certificate:
- macOS: double-click the app, click **Done** on the "Not Opened" dialog, then go to **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to "XRD Tools was blocked", and confirm with your password. (On macOS 15 and later, right-click → Open no longer bypasses this.)
- Windows (SmartScreen): click **More info** → **Run anyway**. If the window comes up blank, install the [WebView2 runtime](https://developer.microsoft.com/microsoft-edge/webview2/).

[HOW_TO_OPEN.md](HOW_TO_OPEN.md) is a plain-language version of these steps; it's also bundled inside both downloads as "How To Open.txt".

> The Windows build is produced by CI but hasn't yet been run on a real Windows machine — treat it as untested until it has.

## Installation (from source)

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
./build/build_mac.sh            # builds, signs, and installs to /Applications
open "/Applications/XRD Tools.app"
```
The script builds into `dist/` (a gitignored workspace), signs a copy outside the repo, and installs it to `/Applications`, replacing any older copy. Use `NO_INSTALL=1 ./build/build_mac.sh` to leave the result in `dist/` only.

**Windows** — PyInstaller can't cross-compile, so this must run *on* a Windows machine (or let CI do it, below):
```bat
build\build_windows.bat
dist\"XRD Tools"\"XRD Tools.exe"
```

### CI and releases

[.github/workflows/build.yml](.github/workflows/build.yml) builds the macOS `.dmg` and Windows `.zip` on every push to `main` and every PR (downloadable from the run's **Artifacts**). Pushing a tag like `v1.0.0` also publishes both to a [GitHub Release](https://github.com/EmilJaffal/xrd-tools-app/releases). Bump `CFBundleShortVersionString` in [build/xrd_tools.spec](build/xrd_tools.spec) to match before tagging.

## Layout

```
xrd_match/            XRD Match tab: create_layout() / register_callbacks(app)
multipattern_xrd/      MultiPattern XRD tab: create_layout(app) / register_callbacks(app)
app_factory.py         builds the one Dash() instance, mounts both tabs
desktop_main.py         pywebview entrypoint (native window)
assets/                CSS scoped per tab (.tab-xrd-match / .tab-multipattern) + shared fonts
build/                 PyInstaller spec + build scripts (mac tested, windows scripted)
HOW_TO_OPEN.md         plain-language open/install guide, bundled into every build
.github/workflows/     CI: builds both platforms; publishes a Release on `v*` tags
```

## Notes

- Each tab's assets are CSS-scoped under `.tab-xrd-match` / `.tab-multipattern` so one tab's font rules can't bleed into the other (both tabs' assets load into the same page).
- `xrd_match/callbacks.py`'s Pawley/Riet `.inp` generators no longer also write to the current working directory (unlike the original web app) — inside a packaged desktop app, cwd may not be writable; the content is delivered entirely through `dcc.Download`.
- Not carried over from the source repos: `make_riet_inps.py` (personal hardcoded paths, unused by the app) and a few dead/duplicate component definitions.

## Troubleshooting

- **`resource fork, Finder information, or similar detritus not allowed`** in the build log: this comes from PyInstaller's own signing step when the project folder lives somewhere Finder/iCloud tags with extra metadata (e.g. an iCloud-synced Desktop). It's harmless: `build_mac.sh` re-signs a copy in a temp folder outside iCloud afterwards, and that's the copy it installs.
- **`.cif`/`.xy` upload buttons don't filter file types in the native window**: the macOS open panel can only grey out files it recognizes by a registered type, and `.cif`/`.xy` aren't standard system types — `build/xrd_tools.spec` registers them as custom UTIs, but a fresh build may need Launch Services to pick that up:
  ```bash
  /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "/Applications/XRD Tools.app"
  ```
  Regardless of what the picker shows, uploading the wrong file type is always rejected with an on-screen error — this only affects how much the OS dialog itself grays out.

## License

[MIT](LICENSE)
