#!/bin/bash
# Build the macOS standalone app: dist/XRD Tools.app
#
# Usage (from anywhere):
#   ./build/build_mac.sh
#
# Requires the project's venv (or any env with requirements.txt installed,
# including pyinstaller) to already be active, OR run this script directly
# and it will create/reuse .venv itself.
set -euo pipefail

cd "$(dirname "$0")/.."   # move to the project root regardless of cwd

if [ ! -d ".venv" ]; then
    echo "Creating .venv ..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Plain `rm -rf` can transiently fail here with "Directory not empty" if
# Finder rewrites .DS_Store in dist/ mid-delete (seen on folders under
# iCloud Desktop sync) — retry a few times instead of letting `set -e` abort
# the whole build over a one-off race.
for _ in 1 2 3 4 5; do
    rm -rf build_output dist && break
    sleep 0.5
done

pyinstaller build/xrd_tools.spec --noconfirm --distpath dist --workpath build_output

# kaleido (used for "Download plot" PNG export) ships its own launcher shell
# script with an UNQUOTED path variable (`cd $DIR`) — this breaks the moment
# the app lives anywhere with a space in the path, which "XRD Tools.app"
# itself guarantees. Without this, every plot download silently no-ops
# (the Python side catches the resulting subprocess failure and swallows it).
# Fix it in place inside the built bundle.
kaleido_launcher="dist/XRD Tools.app/Contents/Resources/kaleido/executable/kaleido"
if [ -f "$kaleido_launcher" ]; then
    cat > "$kaleido_launcher" <<'KALEIDO_EOF'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd "$DIR"
exec "$DIR/bin/kaleido" "$@"
KALEIDO_EOF
    chmod +x "$kaleido_launcher"
fi

# PyInstaller's own ad-hoc signing step can fail with "resource fork, Finder
# information, or similar detritus not allowed" because this repo lives on
# the iCloud-synced Desktop, which keeps re-adding extended attributes inside
# dist/ — even straight after `xattr -cr`. So sign a copy in a temp dir
# outside iCloud instead, then install that signed copy to /Applications
# (and put it back in dist/ so dist/ never holds a broken signature).
# Signing also has to happen *after* the kaleido patch above, or the
# rewritten file would invalidate it. Set NO_INSTALL=1 to skip /Applications.
APP_NAME="XRD Tools"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister
if [ -d "dist/$APP_NAME.app" ]; then
    SIGN_DIR="$(mktemp -d)"
    trap 'rm -rf "$SIGN_DIR"' EXIT
    ditto --norsrc --noextattr "dist/$APP_NAME.app" "$SIGN_DIR/$APP_NAME.app"
    xattr -cr "$SIGN_DIR/$APP_NAME.app"
    codesign -s - --force --deep "$SIGN_DIR/$APP_NAME.app"
    codesign -v "$SIGN_DIR/$APP_NAME.app"

    rm -rf "dist/$APP_NAME.app"
    ditto --norsrc --noextattr "$SIGN_DIR/$APP_NAME.app" "dist/$APP_NAME.app"

    if [ "${NO_INSTALL:-0}" != "1" ]; then
        rm -rf "/Applications/$APP_NAME.app"
        ditto --norsrc --noextattr "$SIGN_DIR/$APP_NAME.app" "/Applications/$APP_NAME.app"
        "$LSREGISTER" -f "/Applications/$APP_NAME.app" 2>/dev/null || true
        echo
        echo "Done. Installed to /Applications/$APP_NAME.app — open it with:"
        echo "  open \"/Applications/$APP_NAME.app\""
        exit 0
    fi
fi

echo
echo "Done. Open it with:"
echo "  open \"dist/$APP_NAME.app\""
