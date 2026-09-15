# PyInstaller spec for XRD Tools.
#
# Build (macOS): from the xrd-tools-app/ directory, with the project venv active:
#   pyinstaller build/xrd_tools.spec --noconfirm
# Produces dist/XRD Tools.app (and dist/XRD Tools/ as the unbundled onedir form).
#
# NOTE: PyInstaller does not cross-compile — building a Windows .exe requires
# running the equivalent command on an actual Windows machine (see
# build/build_windows.bat), or via the CI workflow in build/github-workflows/.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# This spec lives in build/, so the project root is one level up.
PROJECT_ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(PROJECT_ROOT / "assets"), "assets"),
    (str(PROJECT_ROOT / "xrd_match" / "atomic_scattering_params.json"), "xrd_match"),
]
# pymatgen ships its own data files (periodic_table.json.gz, atomic radii
# tables, etc.) that PyInstaller's default analysis doesn't pick up on its
# own — without this, the frozen app crashes on import with a
# FileNotFoundError the first time pymatgen.core is imported.
datas += collect_data_files("pymatgen")
# dash and plotly ship their own static JS/CSS assets the same way.
datas += collect_data_files("dash")
datas += collect_data_files("plotly")

a = Analysis(
    [str(PROJECT_ROOT / "desktop_main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "dash",
        "dash.dash_table",
        "pymatgen.io.cif",
        "pymatgen.symmetry.analyzer",
        "pymatgen.analysis.diffraction.core",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="XRD Tools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(PROJECT_ROOT / "build" / ("icon.ico" if sys.platform == "win32" else "icon.icns")),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="XRD Tools",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="XRD Tools.app",
        icon=str(PROJECT_ROOT / "build" / "icon.icns"),
        bundle_identifier="com.emiljaffal.xrdtools",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
            # Register .cif/.xy as real (exported) UTIs so the native macOS
            # open panel — used for the upload buttons in xrd_match's UI —
            # can actually grey out everything else. Without this, ".cif"/
            # ".xy" aren't MIME/UTI types the system knows, so the panel's
            # accept-based filtering silently no-ops and shows every file.
            # Requires the OS to (re)register Launch Services for this
            # bundle, which normally happens automatically the first time
            # the built .app is launched/moved.
            "UTExportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": "com.emiljaffal.xrdtools.cif",
                    "UTTypeDescription": "Crystallographic Information File",
                    "UTTypeConformsTo": ["public.plain-text"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": ["cif"],
                        "public.mime-type": ["chemical/x-cif"],
                    },
                },
                {
                    "UTTypeIdentifier": "com.emiljaffal.xrdtools.xy",
                    "UTTypeDescription": "XY Diffraction Pattern Data",
                    "UTTypeConformsTo": ["public.plain-text"],
                    "UTTypeTagSpecification": {
                        "public.filename-extension": ["xy"],
                        "public.mime-type": ["text/x-xy-diffraction-data"],
                    },
                },
            ],
        },
    )
