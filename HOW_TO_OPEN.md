How to open XRD Tools
=====================

No installation needed. No Python, no command line, nothing to set up —
just download and open. Everything the app needs is already bundled inside
it.

Download the file for your computer from the Releases page:
https://github.com/EmilJaffal/xrd-tools-app/releases/latest


macOS
-----

This build runs on Apple Silicon Macs (M1 or newer) only.

1. Download `xrd-tools-mac.dmg` and double-click it. A small window opens
   with the app's icon and a shortcut to your Applications folder.

2. Drag the app icon onto the Applications shortcut. This copies it there.

3. Open Applications (or press Cmd+Space, type "XRD Tools", and press
   Return) and double-click the app.

4. The first time you open it, macOS will say "XRD Tools" Not Opened —
   "Apple could not verify it is free of malware." This is expected: it
   shows up for any app that isn't signed with a paid Apple developer
   certificate, and doesn't mean anything is wrong. To allow it, just once:
   - Click **Done** on that message (not "Move to Trash").
   - Open **System Settings → Privacy & Security** and scroll to the bottom.
   - Next to "XRD Tools was blocked to protect your Mac", click
     **Open Anyway**, then **Open Anyway** again and enter your password.
   - From then on, it opens normally with a regular double-click.
   (Older guides say to right-click the app and choose Open — that stopped
   working in macOS 15 Sequoia.)

5. A window opens with the app running. The very first launch can take up
   to a minute while it sets itself up; later launches are much faster.


Windows
-------

1. Download `xrd-tools-windows.zip`. Right-click it and choose
   **Extract All...**, then pick any folder (your Desktop or Documents both
   work fine).

2. Open the extracted folder and double-click `XRD Tools.exe`.

3. Windows will likely show a blue "Windows protected your PC" screen. This
   is Microsoft SmartScreen's standard warning for any app that isn't from a
   large registered publisher — it doesn't mean anything is wrong. To
   continue:
   - Click **More info**.
   - Click **Run anyway**.

4. The app opens in its own window.

5. If the window opens but stays blank: install the free Microsoft Edge
   WebView2 Runtime (almost every Windows 10/11 PC already has it, so this
   is rarely needed):
   https://developer.microsoft.com/microsoft-edge/webview2/


Using the app
-------------

- Two tabs at the top: **XRD Match** (compare CIF-simulated patterns against
  an experimental `.xy` file, tune lattice parameters, and generate TOPAS
  Pawley/Rietveld `.inp` files) and **MultiPattern XRD** (overlay several
  `.xy` patterns at once).
- Plots and `.inp` files you save go to your Downloads folder.
- Everything runs locally on your computer. Nothing you upload or export is
  sent anywhere.


Removing it
-----------

Delete the app (macOS) or the extracted folder (Windows). There's no
separate uninstaller and nothing else gets left behind beyond the files
you've chosen to save.
