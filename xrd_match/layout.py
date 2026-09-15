from dash import html, dcc

# Number of predefined lattice-parameter blocks (one per CIF slot). Shared
# with callbacks.py so the "no more than N CIFs" upload guard always matches
# however many blocks actually exist here.
MAX_CIF_FILES = 6


def create_layout():
    """Build the XRD Match tab's component tree (no Dash() instance owned here)."""

    # Compact "button-style" upload triggers. These replace the old large
    # dashed dropzones — clicking one pops straight to the OS file picker
    # (already scoped to the right extension via `accept`) instead of a
    # permanent drag-and-drop zone sitting on the page.
    upload_btn_style = {
        "height": "36px",
        "padding": "0 16px",
        "display": "inline-flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontSize": "13px",
        "fontWeight": "600",
        "cursor": "pointer",
        "whiteSpace": "nowrap",
    }

    status_style = {
        "marginLeft": "6px",
        "color": "#16a34a",
        "fontSize": "16px",
    }

    # Plain (non-shifted) input style for the a/b/c/α/β/γ boxes, narrow enough
    # for three to sit side by side inside the right-hand sidebar.
    lattice_field_style = {"width": "70px", "height": "32px", "fontSize": "14px", "margin": "6px 0 0"}

    # Predefine lattice parameter blocks for up to MAX_CIF_FILES CIF files.
    # Each block is initially hidden (display: none).
    max_files = MAX_CIF_FILES
    lattice_params_blocks = []
    for i in range(1, max_files + 1):
        block = html.Div(
            id=f"lattice-params-{i}",
            className="panel",
            style={
                "padding": "14px",
                "marginBottom": "10px",
                "display": "none",
                "fontSize": "14px",
            },
            children=[
                # Header row: file name (left) + Reset/Show/Delete (right).
                # A flex row (rather than absolute-positioned buttons) so it
                # never overlaps the header text once the block is narrow.
                html.Div([
                    html.H4(
                        id=f"lattice-params-header-{i}",
                        children=f"CIF File {i}",
                        style={
                            "margin": "0",
                            "fontWeight": "700",
                            "fontSize": "14px",
                            "flex": "1 1 auto",
                            "minWidth": "0",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        }
                    ),
                    html.Div([
                        html.Button(
                            "Reset",
                            id=f"reset-{i}",
                            n_clicks=0,
                            className="btn btn-neutral btn-sm",
                        ),
                        html.Button(
                            # A newly-uploaded CIF starts visible (see
                            # store_cif_files in callbacks.py), so the button
                            # must start on "Hide" — matching that state —
                            # not "Show", which would claim it's hidden.
                            "Hide",
                            id=f"toggle-{i}",
                            n_clicks=0,
                            className="btn btn-sm",
                            style={
                                "backgroundColor": "#eef0fe",
                                "color": "#4f46e5",
                                "border": "1px solid #eef0fe",
                            }
                        ),
                        html.Button(
                            "Delete",
                            id=f"delete-{i}",
                            n_clicks=0,
                            className="btn btn-danger btn-sm",
                        )
                    ], style={"display": "flex", "gap": "6px", "flexShrink": "0", "marginLeft": "8px"})
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),
                # Lattice parameters for each block:

                html.Div([
                    html.Div("Cell parameters", className="field-label", style={"marginBottom": "8px"}),
                    # Row for a, b, c:

                html.Div([
                    html.Div([
                        html.Label("a", className="field-label"),
                        dcc.Input(
                            id=f"lattice-{i}-a",
                            type="number",
                            step="0.01",
                            className="field-input",
                            style=lattice_field_style
                        )
                    ], style={"display": "inline-block", "marginRight": "8px"}),

                    html.Div([
                        html.Label("b", className="field-label"),
                        dcc.Input(
                            id=f"lattice-{i}-b",
                            type="number",
                            step="0.01",
                            className="field-input",
                            style=lattice_field_style
                        )
                    ], style={"display": "inline-block", "marginRight": "8px"}),

                    html.Div([
                        html.Label("c", className="field-label"),
                        dcc.Input(
                            id=f"lattice-{i}-c",
                            type="number",
                            step="0.01",
                            className="field-input",
                            style=lattice_field_style
                        )
                    ], style={"display": "inline-block", "marginRight": "8px"}),

                    html.Div([
                        html.Div([
                            html.Label("α", className="field-label field-label--greek"),
                            dcc.Input(
                                id=f"lattice-{i}-alpha",
                                type="number",
                                className="field-input",
                                style=lattice_field_style
                            )
                        ], style={"display": "inline-block", "marginRight": "8px"}),

                        html.Div([
                            html.Label("β", className="field-label field-label--greek"),
                            dcc.Input(
                                id=f"lattice-{i}-beta",
                                type="number",
                                className="field-input",
                                style=lattice_field_style
                            )
                        ], style={"display": "inline-block", "marginRight": "8px"}),

                        html.Div([
                            html.Label("γ", className="field-label field-label--greek"),
                            dcc.Input(
                                id=f"lattice-{i}-gamma",
                                type="number",
                                className="field-input",
                                style=lattice_field_style
                            )
                        ], style={"display": "inline-block", "marginRight": "8px"})
                    ], style={"display": "flex", "flexWrap": "wrap", "alignItems": "flex-start"})
                ], style={"display": "flex", "flexWrap": "wrap", "gap": "4px"})]),

            html.Div([
                # Intensity scaling slider
                html.Div([
                    html.Div("Intensity scaling", className="field-label", style={"marginBottom": "4px"}),
                    dcc.Slider(
                        id=f"intensity-{i}",
                        min=0,
                        max=150,
                        step=1,
                        value=100,
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"marginRight": "0", "marginTop": "10px", "fontSize": "13px"}),

                # Background level slider
                html.Div([
                    html.Div("Background level", className="field-label", style={"marginBottom": "4px"}),
                    dcc.Slider(
                        id=f"background-{i}",
                        min=0,
                        max=100,
                        step=1,
                        value=0,
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"marginRight": "0", "marginTop": "10px", "fontSize": "13px"}),

                # Shift unit cell slider
                html.Div([
                    html.Div("Shift unit cell", className="field-label", style={"marginBottom": "4px"}),
                    dcc.Slider(
                        id=f"lattice-scale-{i}",
                        min=-5,
                        max=5,
                        step=0.1,
                        value=0,
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"marginRight": "0", "marginTop": "10px", "fontSize": "13px"})
            ], style={"marginTop": "4px"})
            ]
        )
        lattice_params_blocks.append(block)

    return html.Div(
        style={"fontFamily": "Open Sans", "fontSize": "14px"},  # Global font style.
        children=[
            # Header row: title (left) + Refresh (right).
            html.Div(
                children=[
                    html.H2("XRD Pattern Customizer", style={"fontSize": "20px", "fontWeight": "700", "margin": "0", "color": "#1f2430"}),
                    html.Button(
                        "↺ Refresh",
                        id="refresh-all-btn",
                        n_clicks=0,
                        className="btn btn-neutral",
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "padding": "4px 0 14px",
                }
            ),

            # Toolbar: upload triggers + Pawley/Riet generation, all in one
            # compact row instead of two full-width dropzones.
            html.Div([
                html.Div([
                    dcc.Upload(
                        id="upload-xy",
                        children=html.Span("Upload .xy"),
                        multiple=False,
                        # ".xy" isn't a MIME/UTI macOS knows on its own, so the
                        # native picker in the packaged desktop app can't grey
                        # anything out from the extension alone; the second
                        # token is the custom UTI's MIME, registered via
                        # build/xrd_tools.spec's UTExportedTypeDeclarations,
                        # which the picker CAN resolve and filter on — but
                        # only once running from a built, Launch-Services-
                        # registered .app (a plain `python desktop_main.py`
                        # dev run has no Info.plist, so this token is a no-op
                        # there and the OS picker shows everything, same as
                        # before). Non-.xy files are hard-rejected in
                        # callbacks.py either way, regardless of what the OS
                        # dialog lets through.
                        accept=".xy,text/x-xy-diffraction-data",
                        className="btn btn-neutral",
                        style=upload_btn_style
                    ),
                    html.Span(id="xy-upload-status", style=status_style),
                ], style={"display": "inline-flex", "alignItems": "center"}),

                html.Div([
                    dcc.Upload(
                        id="upload-cif",
                        children=html.Span("Upload .cif(s)"),
                        multiple=True,
                        # Same reasoning as upload-xy above.
                        accept=".cif,chemical/x-cif",
                        className="btn btn-neutral",
                        style=upload_btn_style
                    ),
                    html.Span(id="cif-upload-status", style=status_style),
                ], style={"display": "inline-flex", "alignItems": "center", "marginLeft": "10px"}),

                html.Div([
                    html.Button(
                        "Generate Pawley .inp",
                        id="generate-pawley-btn",
                        n_clicks=0,
                        # Starts disabled — nothing is loaded yet to generate
                        # from. A callback re-enables it once there's an .xy
                        # file plus at least one CIF (see callbacks.py).
                        disabled=True,
                        className="btn btn-accent",
                    ),
                    html.Span(id="pawley-copy-status", style={"marginLeft": "8px", "color": "#16a34a", "fontSize": "13px"})
                ], style={"display": "inline-flex", "alignItems": "center", "marginLeft": "16px"}),

                html.Div([
                    html.Button(
                        "Generate Riet .inp",
                        id="generate-riet-btn",
                        n_clicks=0,
                        disabled=True,
                        className="btn btn-accent",
                    ),
                    html.Span(id="riet-copy-status", style={"marginLeft": "8px", "color": "#16a34a", "fontSize": "13px"})
                ], style={"display": "inline-flex", "alignItems": "center", "marginLeft": "10px"}),
            ], className="panel-row", style={"display": "flex", "flexWrap": "wrap", "alignItems": "center", "marginBottom": "12px"}),

            # Pattern opacities, experimental intensity scaling, and 2θ range side by side
            html.Div([
                html.Div([
                    html.Div("Pattern opacities", className="field-label", style={"marginBottom": "4px"}),
                    dcc.Slider(
                        id="opacity-slider",
                        min=0,
                        max=1,
                        step=0.1,
                        value=0.9,
                        marks={i/10: str(i*10) for i in range(11)},
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"fontSize": "13px", "width": "31%", "marginRight": "16px", "display": "inline-block", "verticalAlign": "middle"}),

                html.Div([
                    html.Div("Experimental intensity scaling", className="field-label", style={"marginBottom": "4px"}),
                    dcc.Slider(
                        id="exp-intensity-slider",
                        min=0,
                        max=200,
                        step=1,
                        value=100,
                        marks={i: str(i) for i in range(0, 201, 20)},
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"fontSize": "13px", "width": "31%", "marginRight": "16px", "display": "inline-block", "verticalAlign": "middle"}),

                html.Div([
                    html.Div("2θ range", className="field-label", style={"marginBottom": "4px"}),
                    dcc.RangeSlider(
                        id="xrange-slider",
                        min=0,
                        max=120,
                        step=1,
                        value=[10, 120],
                        marks={i: str(i) for i in range(0, 121, 10)},
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], style={"fontSize": "13px", "width": "31%", "display": "inline-block", "verticalAlign": "middle"})
            ], className="panel-row", style={"marginBottom": "12px", "width": "100%", "display": "flex", "alignItems": "center"}),

            # Main area: plot (left, grows) + scrollable CIF list (right,
            # fixed-width sidebar) so adding more CIFs never grows the page —
            # only the sidebar scrolls.
            html.Div([
                html.Div([
                    html.Div([
                        # A plain button + dcc.Download (same pattern as the
                        # Pawley/Riet .inp downloads below) instead of an
                        # <a href="data:..." download target="_blank">: that
                        # combination is unreliable in the desktop app's
                        # WKWebView, which doesn't honor the `download`
                        # attribute for data: URIs the way a normal browser
                        # does — target="_blank" made it try to *navigate*
                        # the single app window to the raw image instead,
                        # which looked like the whole app "refreshing" rather
                        # than a file actually saving.
                        html.Button("Download plot", id="download-plot-btn", n_clicks=0, className="btn btn-accent"),
                        dcc.Download(id="plot-download"),
                    ], style={"marginBottom": "10px"}),

                    html.Div([
                        # Computing the diffraction pattern (pymatgen) can
                        # take a couple of seconds, especially with several
                        # CIFs loaded — without this the plot area just sits
                        # blank/stale with no sign anything is happening.
                        dcc.Loading(
                            type="circle",
                            children=dcc.Graph(
                                id="xrd-plot",
                                style={"width": "100%", "height": "100%"},
                                # Without this, Plotly renders at its own fixed
                                # default size and ignores how wide the container
                                # actually is — this is what made the graph look
                                # narrow. responsive=True makes it fill/resize
                                # with plot-container.
                                config={"responsive": True}
                            )
                        )
                    ], id="plot-container", style={"width": "100%", "height": "550px"}),
                ], style={"flex": "1 1 auto", "minWidth": "0"}),

                html.Div([
                    html.Div("CIF files", className="field-label", style={"marginBottom": "8px"}),
                    dcc.Loading(
                        type="circle",
                        # Parsing a newly-uploaded CIF (or reflowing the
                        # blocks after a delete) also runs through pymatgen,
                        # so this gets the same "something is happening"
                        # affordance as the plot above.
                        children=html.Div(
                            id="lattice-params-container",
                            children=lattice_params_blocks,
                            style={
                                "maxHeight": "570px",
                                "overflowY": "auto",
                                "paddingRight": "4px",
                            }
                        )
                    ),
                ], style={"width": "340px", "flexShrink": "0", "marginLeft": "14px"}),
            ], style={"display": "flex", "alignItems": "flex-start", "width": "100%"}),

            # Hidden stores.
            dcc.Store(id="cif-store"),
            dcc.Store(id="xy-store"),
            dcc.Store(id="cif-order-store"),
            dcc.Store(id="cif-visibility-store", data={}),
            dcc.Store(id="pawley-content-store"),
            dcc.Store(id="riet-content-store"),
            dcc.Download(id="pawley-download"),
            dcc.Download(id="riet-download")
        ]
    )
