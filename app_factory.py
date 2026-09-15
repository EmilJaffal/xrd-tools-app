"""Builds the single Dash app that hosts both XRD Match and MultiPattern XRD as tabs.

Both sub-apps keep their original component ids (there are no collisions between
them), so both tabs' component trees are simply mounted side by side in one
layout and Dash's dcc.Tabs toggles which one is visible. Because every id is
present in the initial layout, both sub-apps' existing @app.callback
registrations resolve normally with no suppress_callback_exceptions needed.
"""
import sys
from pathlib import Path

from dash import Dash, dcc, html

from xrd_match.layout import create_layout as create_xrd_match_layout
from xrd_match.callbacks import register_callbacks as register_xrd_match_callbacks
from multipattern_xrd.layout import create_layout as create_multipattern_layout
from multipattern_xrd.callbacks import register_callbacks as register_multipattern_callbacks


def _project_root() -> Path:
    """Dash's default `assets_folder` lookup (derived from `__name__`'s module
    file) isn't reliable once PyInstaller freezes this into a bundle — frozen
    code runs from a temp extraction dir (`sys._MEIPASS`) or the app bundle's
    Resources path rather than this source file's real location. Resolve the
    assets folder explicitly so it works the same in dev and once packaged."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def create_app():
    app = Dash(
        __name__,
        title="XRD Tools",
        assets_folder=str(_project_root() / "assets"),
        suppress_callback_exceptions=False,
    )

    app.layout = html.Div([
        html.Div(
            [
                html.Span(className="app-header__dot"),
                html.H1("XRD Tools", className="app-header__title"),
            ],
            className="app-header",
        ),
        dcc.Tabs(
            id="xrd-tools-tabs",
            value="tab-xrd-match",
            className="app-tabs tabs-container",
            parent_className="app-tabs-wrapper",
            children=[
                dcc.Tab(
                    label="XRD Match",
                    value="tab-xrd-match",
                    className="app-tab tab",
                    selected_className="app-tab--selected tab--selected",
                    children=html.Div(
                        create_xrd_match_layout(),
                        className="tab-xrd-match app-body",
                    ),
                ),
                dcc.Tab(
                    label="MultiPattern XRD",
                    value="tab-multipattern",
                    className="app-tab tab",
                    selected_className="app-tab--selected tab--selected",
                    children=html.Div(
                        create_multipattern_layout(app),
                        className="tab-multipattern app-body",
                    ),
                ),
            ],
        )
    ])

    register_xrd_match_callbacks(app)
    register_multipattern_callbacks(app)

    return app


if __name__ == "__main__":
    app = create_app()
    server = app.server
    app.run(debug=True, port=8050)
