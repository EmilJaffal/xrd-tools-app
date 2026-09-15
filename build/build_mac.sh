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

# PyInstaller's own ad-hoc signing step can fail with "resource fork, Finder
# information, or similar detritus not allowed" for the same iCloud-sync
# reason above — strip those extended attributes and re-sign so the app
# isn't left with a broken/partial signature.
if [ -d "dist/XRD Tools.app" ]; then
    xattr -cr "dist/XRD Tools.app" 2>/dev/null || true
    codesign -s - --force --deep "dist/XRD Tools.app"
    /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "dist/XRD Tools.app" 2>/dev/null || true
fi

echo
echo "Done. Open it with:"
echo "  open \"dist/XRD Tools.app\""
