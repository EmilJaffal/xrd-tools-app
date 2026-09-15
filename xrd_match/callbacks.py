import base64
import os
import re
import pandas as pd
from dash import Input, Output, State, callback_context, html, no_update
import plotly.graph_objects as go
from .layout import MAX_CIF_FILES
from .preprocess import parse_xy, parse_cif, XRDCalculator #, normalize_structure
from .plot import plot_xrd
from pymatgen.core import Structure
from pymatgen.io.cif import CifParser
import plotly.io as pio
import io
import json


def _y_axis_ticks(y_range_max):
    """Tick positions/labels for the intensity axis, skipping 0 — the y=0
    gridline already sits right on the x-axis, so a "0" tick label there
    just duplicates it and clutters the corner. Range still starts at 0;
    only the label is omitted. Mirrors what dtick=10 would have placed
    (multiples of 10 up to y_range_max), just without the one at 0."""
    last_multiple_of_10 = (int(y_range_max) // 10) * 10
    vals = list(range(10, last_multiple_of_10 + 1, 10))
    return vals, [str(v) for v in vals]


def _toggle_button_style(is_visible):
    """Shared so the per-CIF Show/Hide button always looks the same whether
    it's set by an explicit click (toggle_cif_visibility) or resynced when a
    slot's occupant changes (update_lattice_params_blocks)."""
    return {
        "backgroundColor": "#eef0fe" if is_visible else "#f1f2f5",
        "color": "#4f46e5" if is_visible else "#6b7280",
        "fontSize": "12px",
        "fontWeight": "600",
        "border": "1px solid",
        "borderColor": "#eef0fe" if is_visible else "#e3e5eb",
        "borderRadius": "6px",
        "padding": "4px 10px",
    }


def _formula_label(text):
    """Split a CIF filename (usually a chemical formula, e.g. "Fe2O3.cif")
    into the plain/digit runs so the per-CIF sidebar header can render the
    numbers as real subscripts (Fe<sub>2</sub>O<sub>3</sub>) instead of
    plain inline digits. Returns a list suitable as an html.H4 `children`."""
    if not text:
        return text
    return [html.Sub(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", text) if part != ""]


def register_callbacks(app):
    """Register every XRD Match callback against the given Dash app instance."""

    # The `accept` attribute on the upload buttons (see layout.py) is a
    # best-effort hint to the browser/OS file picker — Chrome filters by
    # extension directly, but the native macOS panel (used when this runs
    # inside the pywebview desktop window) can only greyscale-filter by a
    # resolvable MIME/UTI, and ".cif"/".xy" aren't registered system MIME
    # types, so that picker may still show everything. These two constants
    # back a hard guarantee that only correctly-named files ever get stored,
    # regardless of what the OS dialog let through.
    CIF_SUFFIX = ".cif"
    XY_SUFFIX = ".xy"

    _status_ok_style = {"marginLeft": "6px", "color": "#16a34a", "fontSize": "16px"}
    _status_err_style = {"marginLeft": "6px", "color": "#e6483f", "fontSize": "13px", "fontWeight": "600"}

    # ------------------------------------------------------------------
    # File Upload Check Mark Callbacks
    # ------------------------------------------------------------------
    # File Upload Check Mark Callbacks are merged into the Store Uploaded
    # Files Callbacks below — both fired on the same Input and previously
    # duplicated the same parse work; combining them also lets the status
    # message actually reflect *why* a file was rejected (wrong extension,
    # over the per-block cap, or unparseable content) instead of just
    # printing that reason to the server console where the user never sees it.

    # ------------------------------------------------------------------
    # Store Uploaded Files Callbacks
    # ------------------------------------------------------------------
    @app.callback(
        Output("xy-store", "data"),
        Output("xy-upload-status", "children"),
        Output("xy-upload-status", "style"),
        Input("upload-xy", "contents"),
        State("upload-xy", "filename")
    )
    def store_xy_file(contents, filename):
        if contents is None:
            return no_update, "", _status_ok_style
        if not filename or not filename.lower().endswith(XY_SUFFIX):
            print("Rejected non-.xy upload:", filename)
            return no_update, "✗ .xy files only", _status_err_style
        try:
            df = parse_xy(contents)
            max_intensity = df['intensity'].max()
            df['intensity'] = (df['intensity'] / max_intensity) * 100
            return df.to_json(date_format='iso', orient='split'), "✓", _status_ok_style
        except Exception as e:
            print("Error processing XY file:", e)
            return no_update, "✗ couldn't read that file", _status_err_style

    @app.callback(
        [Output("cif-store", "data"),
         Output("cif-order-store", "data"),
         Output("cif-visibility-store", "data", allow_duplicate=True),
         Output("cif-upload-status", "children"),
         Output("cif-upload-status", "style")],
        Input("upload-cif", "contents"),
        State("upload-cif", "filename"),
        State("cif-store", "data"),
        State("cif-order-store", "data"),
        State("cif-visibility-store", "data"),
        prevent_initial_call=True
    )
    def store_cif_files(contents_list, filenames, existing_data, existing_order, visibility_state):
        if contents_list is None:
            return (existing_data if existing_data is not None else no_update,
                    existing_order if existing_order is not None else no_update,
                    no_update, "", _status_ok_style)

        cif_data = existing_data.copy() if existing_data else {}
        cif_order = existing_order.copy() if existing_order else []
        visibility = visibility_state.copy() if visibility_state else {}

        skipped_ext = []
        skipped_cap = []
        skipped_unparseable = []

        for contents, name in zip(contents_list, filenames):
            if not name.lower().endswith(CIF_SUFFIX):
                print("Skipping non-.cif upload:", name)
                skipped_ext.append(name)
                continue
            if name not in cif_order and len(cif_order) >= MAX_CIF_FILES:
                print(f"Skipping CIF beyond the {MAX_CIF_FILES}-file limit:", name)
                skipped_cap.append(name)
                continue
            try:
                # Validate it actually parses *before* storing it, so a
                # corrupt/wrong-format file never silently occupies a slot
                # with no visible sign anything went wrong.
                parse_cif(contents)
            except Exception as e:
                print("Skipping unparseable CIF:", name, "-", e)
                skipped_unparseable.append(name)
                continue
            if name not in cif_order:
                cif_order.append(name)
                visibility[name] = True  # New CIFs are visible by default
            cif_data[name] = contents

        problems = []
        if skipped_ext:
            problems.append(f"{len(skipped_ext)} not .cif")
        if skipped_cap:
            problems.append(f"{len(skipped_cap)} over the {MAX_CIF_FILES}-file limit")
        if skipped_unparseable:
            problems.append(f"{len(skipped_unparseable)} unreadable")

        if problems:
            status_text, status_style = f"✗ {', '.join(problems)}", _status_err_style
        else:
            status_text, status_style = "✓", _status_ok_style

        return cif_data, cif_order, visibility, status_text, status_style

    # ------------------------------------------------------------------
    # Lattice Parameter Blocks Update Callback
    # ------------------------------------------------------------------
    @app.callback(
        [Output(f"lattice-params-{i}", "style") for i in range(1, 7)] +
        [Output(f"lattice-params-header-{i}", "children") for i in range(1, 7)] +
        # `title` carries the plain filename (also shown as a hover tooltip)
        # — `children` now holds rich Sub-formatted display content instead
        # of a plain string, so it can no longer double as the stable key
        # the other per-block callbacks below use to look up cif_data.
        [Output(f"lattice-params-header-{i}", "title") for i in range(1, 7)] +
        [Output(f"lattice-{i}-a", "value") for i in range(1, 7)] +
        [Output(f"lattice-{i}-b", "value") for i in range(1, 7)] +
        [Output(f"lattice-{i}-c", "value") for i in range(1, 7)] +
        [Output(f"lattice-{i}-alpha", "value") for i in range(1, 7)] +
        [Output(f"lattice-{i}-beta", "value") for i in range(1, 7)] +
        [Output(f"lattice-{i}-gamma", "value") for i in range(1, 7)] +
        [Output(f"lattice-scale-{i}", "value", allow_duplicate=True) for i in range(1, 7)] +
        [Output(f"lattice-{i}-a", "style", allow_duplicate=True) for i in range(1, 7)] +
        [Output(f"lattice-{i}-b", "style", allow_duplicate=True) for i in range(1, 7)] +
        [Output(f"lattice-{i}-c", "style", allow_duplicate=True) for i in range(1, 7)] +
        # Resync each slot's Show/Hide button to the *actual* occupant's
        # visibility whenever the occupant changes (upload/delete), instead
        # of leaving whatever label/style the slot's previous occupant left
        # behind — that mismatch is what made a freshly-uploaded CIF (visible
        # by default) sometimes start on a stale "Show" button.
        [Output(f"toggle-{i}", "children", allow_duplicate=True) for i in range(1, 7)] +
        [Output(f"toggle-{i}", "style", allow_duplicate=True) for i in range(1, 7)],
        Input("cif-store", "data"),
        Input("cif-order-store", "data"),
        [State(f"lattice-{i}-a", "value") for i in range(1, 7)] +
        [State(f"lattice-{i}-b", "value") for i in range(1, 7)] +
        [State(f"lattice-{i}-c", "value") for i in range(1, 7)] +
        [State(f"lattice-{i}-alpha", "value") for i in range(1, 7)] +
        [State(f"lattice-{i}-beta", "value") for i in range(1, 7)] +
        [State(f"lattice-{i}-gamma", "value") for i in range(1, 7)] +
        [State(f"lattice-params-header-{i}", "title") for i in range(1, 7)] +
        [State("cif-visibility-store", "data")],
        prevent_initial_call='initial_duplicate'
    )
    def update_lattice_params_blocks(cif_data, cif_order,
                                     a1, a2, a3, a4, a5, a6,
                                     b1, b2, b3, b4, b5, b6,
                                     c1, c2, c3, c4, c5, c6,
                                     alpha1, alpha2, alpha3, alpha4, alpha5, alpha6,
                                     beta1, beta2, beta3, beta4, beta5, beta6,
                                     gamma1, gamma2, gamma3, gamma4, gamma5, gamma6,
                                     prev_header1, prev_header2, prev_header3, prev_header4, prev_header5, prev_header6,
                                     visibility_state):
        style_outputs = []
        header_outputs = []
        title_outputs = []
        a_outputs = []
        b_outputs = []
        c_outputs = []
        alpha_outputs = []
        beta_outputs = []
        gamma_outputs = []
        scale_outputs = []
        a_style_outputs = []
        b_style_outputs = []
        c_style_outputs = []
        toggle_text_outputs = []
        toggle_style_outputs = []
        current_a = [a1, a2, a3, a4, a5, a6]
        current_b = [b1, b2, b3, b4, b5, b6]
        current_c = [c1, c2, c3, c4, c5, c6]
        current_alpha = [alpha1, alpha2, alpha3, alpha4, alpha5, alpha6]
        current_beta = [beta1, beta2, beta3, beta4, beta5, beta6]
        current_gamma = [gamma1, gamma2, gamma3, gamma4, gamma5, gamma6]
        prev_headers = [prev_header1, prev_header2, prev_header3, prev_header4, prev_header5, prev_header6]
        visibility_state = visibility_state or {}

        # Plain (non-shifted) input style, matching reset_block's default.
        default_field_style = {
            "width": "70px",
            "height": "32px",
            "fontSize": "14px",
            "margin": "6px 0 0"
        }

        file_names = cif_order if cif_order else []
        num_files = len(file_names)

        for i in range(6):
            if i < num_files:
                try:
                    structure = parse_cif(cif_data[file_names[i]])
                    # structure = normalize_structure(structure)
                    lattice = structure.lattice
                    # Blocks stack in a single-column, independently-scrolling
                    # sidebar now, so each visible block just takes the full
                    # sidebar width. (border/radius/shadow come from .panel)
                    style_outputs.append({
                        "display": "block",
                        "padding": "14px",
                        "marginBottom": "10px",
                        "fontSize": "14px"
                    })
                    header_outputs.append(_formula_label(file_names[i]))
                    title_outputs.append(file_names[i])
                    is_visible = visibility_state.get(file_names[i], True)
                    toggle_text_outputs.append("Hide" if is_visible else "Show")
                    toggle_style_outputs.append(_toggle_button_style(is_visible))

                    # A slot's *occupant* can change (e.g. a CIF earlier in the list gets
                    # deleted and this slot's CIF shifts up) even though the slot's a/b/c/...
                    # input boxes still hold whatever the previous occupant last displayed.
                    # Detect that and force a fresh recompute instead of keeping stale values.
                    slot_changed = prev_headers[i] != file_names[i]

                    if slot_changed or current_a[i] is None:
                        a_outputs.append(round(lattice.a, 4))
                    else:
                        a_outputs.append(current_a[i])
                    if slot_changed or current_b[i] is None:
                        b_outputs.append(round(lattice.b, 4))
                    else:
                        b_outputs.append(current_b[i])
                    if slot_changed or current_c[i] is None:
                        c_outputs.append(round(lattice.c, 4))
                    else:
                        c_outputs.append(current_c[i])
                    if slot_changed or current_alpha[i] is None:
                        alpha_outputs.append(round(lattice.alpha, 4))
                    else:
                        alpha_outputs.append(current_alpha[i])
                    if slot_changed or current_beta[i] is None:
                        beta_outputs.append(round(lattice.beta, 4))
                    else:
                        beta_outputs.append(current_beta[i])
                    if slot_changed or current_gamma[i] is None:
                        gamma_outputs.append(round(lattice.gamma, 4))
                    else:
                        gamma_outputs.append(current_gamma[i])

                    if slot_changed:
                        # New occupant: the old shift percentage/style no longer applies.
                        scale_outputs.append(0)
                        a_style_outputs.append(default_field_style)
                        b_style_outputs.append(default_field_style)
                        c_style_outputs.append(default_field_style)
                    else:
                        scale_outputs.append(no_update)
                        a_style_outputs.append(no_update)
                        b_style_outputs.append(no_update)
                        c_style_outputs.append(no_update)
                except Exception as e:
                    print("Error parsing CIF for lattice block:", e)
                    style_outputs.append({"display": "none"})
                    header_outputs.append("")
                    title_outputs.append("")
                    toggle_text_outputs.append("Hide")
                    toggle_style_outputs.append(_toggle_button_style(True))
                    a_outputs.append(None)
                    b_outputs.append(None)
                    c_outputs.append(None)
                    alpha_outputs.append(None)
                    beta_outputs.append(None)
                    gamma_outputs.append(None)
                    scale_outputs.append(0)
                    a_style_outputs.append(default_field_style)
                    b_style_outputs.append(default_field_style)
                    c_style_outputs.append(default_field_style)
            else:
                style_outputs.append({"display": "none"})
                header_outputs.append("")
                title_outputs.append("")
                toggle_text_outputs.append("Hide")
                toggle_style_outputs.append(_toggle_button_style(True))
                a_outputs.append(None)
                b_outputs.append(None)
                c_outputs.append(None)
                alpha_outputs.append(None)
                beta_outputs.append(None)
                gamma_outputs.append(None)
                # Reset a freed slot so it doesn't keep a stale shifted look if reused later.
                if prev_headers[i]:
                    scale_outputs.append(0)
                    a_style_outputs.append(default_field_style)
                    b_style_outputs.append(default_field_style)
                    c_style_outputs.append(default_field_style)
                else:
                    scale_outputs.append(no_update)
                    a_style_outputs.append(no_update)
                    b_style_outputs.append(no_update)
                    c_style_outputs.append(no_update)

        return (style_outputs + header_outputs + title_outputs + a_outputs + b_outputs + c_outputs +
                alpha_outputs + beta_outputs + gamma_outputs +
                scale_outputs + a_style_outputs + b_style_outputs + c_style_outputs +
                toggle_text_outputs + toggle_style_outputs)

    # ------------------------------------------------------------------
    # Reset Button Callbacks (One per block)
    # ------------------------------------------------------------------
    def make_reset_callback(i):
        @app.callback(
            [Output(f"lattice-{i}-a", "value", allow_duplicate=True),
             Output(f"lattice-{i}-b", "value", allow_duplicate=True),
             Output(f"lattice-{i}-c", "value", allow_duplicate=True),
             Output(f"lattice-{i}-alpha", "value", allow_duplicate=True),
             Output(f"lattice-{i}-beta", "value", allow_duplicate=True),
             Output(f"lattice-{i}-gamma", "value", allow_duplicate=True),
             Output(f"lattice-scale-{i}", "value"),
             Output(f"lattice-{i}-a", "style", allow_duplicate=True),
             Output(f"lattice-{i}-b", "style", allow_duplicate=True),
             Output(f"lattice-{i}-c", "style", allow_duplicate=True)],
            Input(f"reset-{i}", "n_clicks"),
            [State("cif-store", "data"),
             State(f"lattice-params-header-{i}", "title")],
            prevent_initial_call='initial_duplicate'
        )
        def reset_block(n_clicks, cif_data, file_name):
            if not cif_data or not file_name:
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
            try:
                structure = parse_cif(cif_data[file_name])
                # structure = normalize_structure(structure)
                lattice = structure.lattice
            
                # Default style (no "shifted" highlight)
                default_style = {
                    "width": "70px",
                    "height": "32px",
                    "fontSize": "14px",
                    "margin": "6px 0 0"
                }
            
                return (round(lattice.a, 4),
                        round(lattice.b, 4),
                        round(lattice.c, 4),
                        round(lattice.alpha, 4),
                        round(lattice.beta, 4),
                        round(lattice.gamma, 4),
                        0,  # Reset shift slider to 0
                        default_style,
                        default_style,
                        default_style)
            except Exception as e:
                print("Error in reset callback for", file_name, ":", e)
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        return reset_block

    for i in range(1, 7):
        make_reset_callback(i)

    # ------------------------------------------------------------------
    # Shift Unit Cell Callbacks (Update a, b, c values and styles)
    # ------------------------------------------------------------------
    def make_shift_callback(i):
        @app.callback(
            [Output(f"lattice-{i}-a", "value", allow_duplicate=True),
             Output(f"lattice-{i}-b", "value", allow_duplicate=True),
             Output(f"lattice-{i}-c", "value", allow_duplicate=True),
             Output(f"lattice-{i}-a", "style"),
             Output(f"lattice-{i}-b", "style"),
             Output(f"lattice-{i}-c", "style")],
            Input(f"lattice-scale-{i}", "value"),
            [State("cif-store", "data"),
             State(f"lattice-params-header-{i}", "title")],
            prevent_initial_call='initial_duplicate'
        )
        def shift_unit_cell(scale_value, cif_data, file_name):
            if not cif_data or not file_name or scale_value is None:
                return no_update, no_update, no_update, no_update, no_update, no_update
            try:
                structure = parse_cif(cif_data[file_name])
                lattice = structure.lattice
            
                # Calculate scale factor
                scale_factor = 1 + (scale_value / 100)
            
                # Calculate new values
                new_a = round(lattice.a * scale_factor, 4)
                new_b = round(lattice.b * scale_factor, 4)
                new_c = round(lattice.c * scale_factor, 4)
            
                # Determine style based on whether shifted
                if scale_value != 0:
                    # Accent highlight when shifted
                    input_style = {
                        "width": "70px",
                        "height": "32px",
                        "fontSize": "14px",
                        "margin": "6px 0 0",
                        "color": "#4f46e5",
                        "fontWeight": "700",
                        "borderColor": "#4f46e5"
                    }
                else:
                    # Default style
                    input_style = {
                        "width": "70px",
                        "height": "32px",
                        "fontSize": "14px",
                        "margin": "6px 0 0"
                    }
            
                return new_a, new_b, new_c, input_style, input_style, input_style
            except Exception as e:
                print("Error in shift callback for", file_name, ":", e)
                return no_update, no_update, no_update, no_update, no_update, no_update
        return shift_unit_cell

    for i in range(1, 7):
        make_shift_callback(i)

    # ------------------------------------------------------------------
    # Delete Button Callbacks (One per block)
    # ------------------------------------------------------------------
    def make_delete_callback(i):
        @app.callback(
            [Output("cif-store", "data", allow_duplicate=True),
             Output("cif-order-store", "data", allow_duplicate=True),
             Output("cif-visibility-store", "data", allow_duplicate=True)],
            Input(f"delete-{i}", "n_clicks"),
            [State("cif-store", "data"),
             State("cif-order-store", "data"),
             State("cif-visibility-store", "data"),
             State(f"lattice-params-header-{i}", "title")],
            prevent_initial_call='initial_duplicate'
        )
        def delete_block(n_clicks, cif_data, cif_order, visibility_state, file_name):
            if not cif_data or not file_name:
                return no_update, no_update, no_update
            if n_clicks and file_name in cif_data:
                new_data = cif_data.copy()
                new_order = cif_order.copy() if cif_order else []
                new_visibility = visibility_state.copy() if visibility_state else {}
                new_data.pop(file_name)
                if file_name in new_order:
                    new_order.remove(file_name)
                if file_name in new_visibility:
                    new_visibility.pop(file_name)
                return new_data, new_order, new_visibility
            return cif_data, cif_order, visibility_state
        return delete_block

    for i in range(1, 7):
        make_delete_callback(i)

    # ------------------------------------------------------------------
    # Toggle Visibility Button Callbacks (One per block)
    # ------------------------------------------------------------------
    def make_toggle_callback(i):
        @app.callback(
            [Output(f"toggle-{i}", "children", allow_duplicate=True),
             Output(f"toggle-{i}", "style", allow_duplicate=True),
             Output("cif-visibility-store", "data", allow_duplicate=True)],
            Input(f"toggle-{i}", "n_clicks"),
            [State("cif-visibility-store", "data"),
             State(f"lattice-params-header-{i}", "title")],
            prevent_initial_call='initial_duplicate'
        )
        def toggle_cif_visibility(n_clicks, visibility_state, file_name):
            if not file_name or not visibility_state:
                return no_update, no_update, no_update

            new_visibility = visibility_state.copy()
            current_state = new_visibility.get(file_name, True)
            new_state = not current_state
            new_visibility[file_name] = new_state

            button_text = "Hide" if new_state else "Show"
            return button_text, _toggle_button_style(new_state), new_visibility
        return toggle_cif_visibility

    for i in range(1, 7):
        make_toggle_callback(i)

    # ------------------------------------------------------------------
    # Refresh Button Callback (clears every upload, store, and control back
    # to its starting state). Clearing cif-store/cif-order-store/xy-store is
    # enough to cascade through the existing callback graph and clear the
    # lattice-param blocks, the plot, the download link, and the Pawley/Riet
    # copy statuses on its own — this callback only needs to reset the
    # values nothing else already resets.
    # ------------------------------------------------------------------
    @app.callback(
        [Output("upload-xy", "contents"),
         Output("upload-xy", "filename"),
         Output("upload-cif", "contents"),
         Output("upload-cif", "filename"),
         Output("cif-store", "data", allow_duplicate=True),
         Output("cif-order-store", "data", allow_duplicate=True),
         Output("cif-visibility-store", "data", allow_duplicate=True),
         Output("xy-store", "data", allow_duplicate=True),
         Output("pawley-content-store", "data", allow_duplicate=True),
         Output("riet-content-store", "data", allow_duplicate=True),
         Output("opacity-slider", "value"),
         Output("exp-intensity-slider", "value"),
         Output("xrange-slider", "value")] +
        [Output(f"intensity-{i}", "value") for i in range(1, 7)] +
        [Output(f"background-{i}", "value") for i in range(1, 7)],
        Input("refresh-all-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def refresh_all(n_clicks):
        if not n_clicks:
            return [no_update] * 25
        return (
            [None, None, None, None, None, [], {}, None, None, None, 0.9, 100, [10, 120]]
            + [100] * 6  # intensity sliders back to 100
            + [0] * 6    # background sliders back to 0
        )

    # ------------------------------------------------------------------
    # XRD Plot Callback (Using Dynamic Lattice Parameters and per-CIF intensity/background)
    # ------------------------------------------------------------------
    @app.callback(
        Output("xrd-plot", "figure"),
        [
            Input("xy-store", "data"),
            Input("opacity-slider", "value"),
            Input("exp-intensity-slider", "value"),  
            Input("xrange-slider", "value"),
            # Lattice parameter inputs for blocks 1 to 6.
            Input("lattice-1-a", "value"),
            Input("lattice-2-a", "value"),
            Input("lattice-3-a", "value"),
            Input("lattice-4-a", "value"),
            Input("lattice-5-a", "value"),
            Input("lattice-6-a", "value"),
            Input("lattice-1-b", "value"),
            Input("lattice-2-b", "value"),
            Input("lattice-3-b", "value"),
            Input("lattice-4-b", "value"),
            Input("lattice-5-b", "value"),
            Input("lattice-6-b", "value"),
            Input("lattice-1-c", "value"),
            Input("lattice-2-c", "value"),
            Input("lattice-3-c", "value"),
            Input("lattice-4-c", "value"),
            Input("lattice-5-c", "value"),
            Input("lattice-6-c", "value"),
            Input("lattice-1-alpha", "value"),
            Input("lattice-2-alpha", "value"),
            Input("lattice-3-alpha", "value"),
            Input("lattice-4-alpha", "value"),
            Input("lattice-5-alpha", "value"),
            Input("lattice-6-alpha", "value"),
            Input("lattice-1-beta", "value"),
            Input("lattice-2-beta", "value"),
            Input("lattice-3-beta", "value"),
            Input("lattice-4-beta", "value"),
            Input("lattice-5-beta", "value"),
            Input("lattice-6-beta", "value"),
            Input("lattice-1-gamma", "value"),
            Input("lattice-2-gamma", "value"),
            Input("lattice-3-gamma", "value"),
            Input("lattice-4-gamma", "value"),
            Input("lattice-5-gamma", "value"),
            Input("lattice-6-gamma", "value"),
            Input("lattice-scale-1", "value"),
            Input("lattice-scale-2", "value"),
            Input("lattice-scale-3", "value"),
            Input("lattice-scale-4", "value"),
            Input("lattice-scale-5", "value"),
            Input("lattice-scale-6", "value"),
            Input("intensity-1", "value"),
            Input("intensity-2", "value"),
            Input("intensity-3", "value"),
            Input("intensity-4", "value"),
            Input("intensity-5", "value"),
            Input("intensity-6", "value"),
            Input("background-1", "value"),
            Input("background-2", "value"),
            Input("background-3", "value"),
            Input("background-4", "value"),
            Input("background-5", "value"),
            Input("background-6", "value"),
            Input("cif-visibility-store", "data")
        ],
        State("cif-store", "data"),
        State("cif-order-store", "data"),
        State("upload-xy", "filename")
    )
    def update_xrd_plot(xy_data, opacity, exp_intensity, xrange,
                        a1, a2, a3, a4, a5, a6,
                        b1, b2, b3, b4, b5, b6,
                        c1, c2, c3, c4, c5, c6,
                        alpha1, alpha2, alpha3, alpha4, alpha5, alpha6,
                        beta1, beta2, beta3, beta4, beta5, beta6,
                        gamma1, gamma2, gamma3, gamma4, gamma5, gamma6,
                        scale1, scale2, scale3, scale4, scale5, scale6,
                        intensity1, intensity2, intensity3, intensity4, intensity5, intensity6,
                        background1, background2, background3, background4, background5, background6,
                        visibility_state,
                        cif_data, cif_order, xy_filename):

        file_names = cif_order if cif_order else []
    
        # Parse experimental data first (before checking cif_data)
        exp_data = None  # Default to None if xy_data is not provided
        xrange_min, xrange_max = xrange
    
        # Check if xy_data is not None or empty
        if xy_data:
            try:
                # Manually parse the JSON string
                parsed_data = json.loads(xy_data)

                # Create DataFrame from the parsed data
                exp_data = pd.DataFrame(parsed_data['data'], columns=parsed_data['columns'], index=parsed_data['index'])
                # Scale experimental intensity
                if exp_intensity is not None and exp_data is not None:
                    exp_data['intensity'] = exp_data['intensity'] * (exp_intensity / 100)

                # Filter experimental data based on xrange
                col_candidates = ['two_theta', 'x', 'angle']
                col = next((c for c in col_candidates if c in exp_data.columns), exp_data.columns[0])
                exp_data = exp_data[(exp_data[col] >= xrange_min) & (exp_data[col] <= xrange_max)]

            except ValueError as e:
                exp_data = None

        # If no CIF data, but we have experimental data, plot just that
        if cif_data is None or len(file_names) == 0:
            if exp_data is not None:
                fig = plot_xrd([], [], "CuKa", experimental_data=exp_data, opacity=opacity, exp_filename=xy_filename, intensity_values=[])
                tickvals, ticktext = _y_axis_ticks(105)
                fig.update_layout(
                    yaxis=dict(
                        range=[0, 105],
                        tickmode='array',
                        tickvals=tickvals,
                        ticktext=ticktext,
                        showgrid=False
                    ),
                    legend=dict(borderwidth=0)
                )
                return fig
            else:
                return {}
    
        patterns = []
        titles = []
        num_files = len(file_names)
        a_vals = [a1, a2, a3, a4, a5, a6]
        b_vals = [b1, b2, b3, b4, b5, b6]
        c_vals = [c1, c2, c3, c4, c5, c6]
        alpha_vals = [alpha1, alpha2, alpha3, alpha4, alpha5, alpha6]
        beta_vals = [beta1, beta2, beta3, beta4, beta5, beta6]
        gamma_vals = [gamma1, gamma2, gamma3, gamma4, gamma5, gamma6]
        scale_vals = [scale1, scale2, scale3, scale4, scale5, scale6]
        intensity_vals = [intensity1, intensity2, intensity3, intensity4, intensity5, intensity6]
        background_vals = [background1, background2, background3, background4, background5, background6]

        for i in range(num_files):
            file_name = file_names[i]
        
            # Check if this CIF should be visible
            if visibility_state and file_name in visibility_state and not visibility_state[file_name]:
                continue
        
            try:
                structure = parse_cif(cif_data[file_name])
                # structure = normalize_structure(structure)
            except Exception as e:
                print("Error parsing CIF for", file_name, ":", e)
                continue
            try:
                # a_vals/b_vals/c_vals already reflect the "Shift unit cell" percentage —
                # shift_unit_cell() writes the scaled value straight into these input boxes.
                # Re-applying scale_vals[i] here would square the shift (e.g. +5% would
                # render as ~+10.25%, -5% as ~-9.75%), so just use them as-is.
                new_a = a_vals[i]
                new_b = b_vals[i]
                new_c = c_vals[i]
                new_alpha = alpha_vals[i]
                new_beta = beta_vals[i]
                new_gamma = gamma_vals[i]
                new_lattice = structure.lattice.from_parameters(new_a, new_b, new_c, new_alpha, new_beta, new_gamma)
                # Rebuild structure preserving all site occupancies
                new_structure = Structure(
                    new_lattice,
                    [site.species for site in structure.sites],
                    [site.frac_coords for site in structure.sites],
                    coords_are_cartesian=False
                )
            except Exception as e:
                print("Error updating lattice for", file_name, ":", e)
                new_structure = structure

            calculator = XRDCalculator(wavelength="CuKa")
            try:
                pattern = calculator.get_pattern(new_structure, two_theta_range=(xrange_min, xrange_max))
            except Exception as e:
                print("Error in XRD calculation for", file_name, ":", e)
                continue

            # Work on a fresh copy of the original intensities
            orig_y = list(pattern.y)
            # Apply intensity scaling (per CIF)
            if intensity_vals[i] is not None and intensity_vals[i] != 100:
                scaled_y = [val * (intensity_vals[i] / 100) for val in orig_y]
            else:
                scaled_y = orig_y
            # Add the background offset (non-cumulatively)
            if background_vals[i] is not None and background_vals[i] > 0:
                new_y = [val + background_vals[i] for val in scaled_y]
            else:
                new_y = scaled_y
            pattern.y = new_y

            patterns.append(pattern)
            titles.append(file_name)
    
        # Prepare intensity values for composition calculation (only for visible CIFs)
        active_intensities = []
        for i in range(num_files):
            file_name = file_names[i]
            # Check if this CIF is visible
            is_visible = not (visibility_state and file_name in visibility_state and not visibility_state[file_name])
            if is_visible and intensity_vals[i] is not None:
                active_intensities.append(intensity_vals[i])
            elif is_visible:
                active_intensities.append(100)
    
        if not active_intensities:  # If all are None or hidden, use empty list
            active_intensities = []

        fig = plot_xrd(patterns, titles, "CuKa", experimental_data=exp_data, opacity=opacity, exp_filename=xy_filename, intensity_values=active_intensities)
    
        max_y_list = [max(pattern.y) for pattern in patterns if pattern.y is not None and len(pattern.y) > 0]
        max_y = max(max_y_list) if max_y_list else 100
        y_range_max = max(105, max_y + 5)
        tickvals, ticktext = _y_axis_ticks(y_range_max)
        fig.update_layout(
            yaxis=dict(
                range=[0, y_range_max],
                tickmode='array',
                tickvals=tickvals,
                ticktext=ticktext,
                showgrid=False
            ),
            legend=dict(borderwidth=0)
        )
        return fig

    # ------------------------------------------------------------------
    # Legend Click Callback (Toggle trace visibility)
    # ------------------------------------------------------------------
    @app.callback(
        Output("xrd-plot", "figure", allow_duplicate=True),
        Input("xrd-plot", "clickData"),
        State("xrd-plot", "figure"),
        prevent_initial_call=True
    )
    def toggle_trace_visibility(click_data, figure):
        if not click_data or not figure:
            return figure
    
        try:
            # Get the trace name from the clicked legend item
            curve_number = click_data.get('points', [{}])[0].get('curveNumber')
            if curve_number is None:
                return figure
        
            # Create a copy of the figure to modify
            fig = go.Figure(figure)
        
            # Toggle the visible property of the clicked trace
            # visible can be True, False, or "legendonly"
            if curve_number < len(fig.data):
                current_visible = fig.data[curve_number].visible
                # Toggle between True and False (or "legendonly")
                if current_visible is True or current_visible is None:
                    fig.data[curve_number].visible = False
                else:
                    fig.data[curve_number].visible = True
        
            return fig
        except Exception as e:
            print("Error in toggle_trace_visibility:", e)
            return figure

    # ------------------------------------------------------------------
    # Download Plot Callback
    # ------------------------------------------------------------------
    @app.callback(
        Output("plot-download", "data"),
        Input("download-plot-btn", "n_clicks"),
        State("xrd-plot", "figure"),
        State("upload-xy", "filename"),
        prevent_initial_call=True
    )
    def download_plot_png(n_clicks, figure, xy_filename):
        download_name = "xrd_pattern.png"
        if xy_filename:
            stem, ext = os.path.splitext(os.path.basename(xy_filename))
            if stem and ext.lower() == ".xy":
                download_name = f"{stem}_xrd.png"

        if not figure:
            return no_update
        try:
            fig = go.Figure(figure)
            fig.update_layout(
                width=1800,
                height=400,
                paper_bgcolor='white',
                plot_bgcolor='white',
                font=dict(size=14),
                margin=dict(l=50, r=50, t=50, b=50),
                showlegend=True,
                legend=dict(borderwidth=0)
            )
            pio.kaleido.scope.mathjax = None
            img_bytes = pio.to_image(
                fig,
                format="png",
                scale=2,
                engine="kaleido",
                width=1800,
                height=400,
                validate=False
            )
            b64_str = base64.b64encode(img_bytes).decode("ascii")
            return {"content": b64_str, "filename": download_name, "type": "image/png", "base64": True}
        except Exception as e:
            print("Error generating plot download:", e)
            return no_update

    # ------------------------------------------------------------------
    # Enable/disable the Generate Pawley/Riet buttons — both need an .xy
    # file and at least one CIF loaded, otherwise they'd just produce an
    # empty/meaningless .inp.
    # ------------------------------------------------------------------
    @app.callback(
        Output("generate-pawley-btn", "disabled"),
        Output("generate-riet-btn", "disabled"),
        Input("xy-store", "data"),
        Input("cif-order-store", "data"),
    )
    def toggle_generate_buttons(xy_data, cif_order):
        ready = bool(xy_data) and bool(cif_order)
        return not ready, not ready

    # ------------------------------------------------------------------
    # Pawley .inp Generation & Clipboard Copy
    # ------------------------------------------------------------------
    def _extract_space_group(cif_contents, structure=None):
        try:
            content_type, content_string = cif_contents.split(',')
            decoded = base64.b64decode(content_string).decode('utf-8', errors='ignore')
            parser = CifParser(io.StringIO(decoded))
            cif_dict = parser.as_dict()
            if cif_dict:
                first_key = list(cif_dict.keys())[0]
                data = cif_dict[first_key]
                for key in data.keys():
                    if key.lower() in ("_space_group_name_h-m_alt", "_symmetry_space_group_name_h-m"):
                        value = data[key]
                        if isinstance(value, list):
                            value = value[0]
                        value = value.strip().strip("'").strip('"')
                        return "".join(value.split())
        except Exception as e:
            print("Error extracting space group:", e)
        if structure is not None:
            try:
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                sg = SpacegroupAnalyzer(structure).get_space_group_symbol()
                return "".join(sg.split())
            except Exception as e:
                print("Fallback space group error:", e)
        return ""

    def _format_lattice_line_with_tag(param, value, tag=None):
        # An axis with no equal partner still needs to be independently refined,
        # so fall back to a plain "@" rather than emitting no refine tag at all.
        marker = tag if tag else "@"
        return f"\t\t{param} {marker}  {value:.6f}"

    def _lpa_equal(v1, v2, decimals=4):
        return round(float(v1), decimals) == round(float(v2), decimals)

    def _clean_cif_value(value):
        if isinstance(value, list):
            value = value[0] if value else ""
        if value is None:
            return ""
        return str(value).strip().strip("'").strip('"')

    def _as_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _format_coord(value):
        text = f"{_as_float(value):.6f}".rstrip("0").rstrip(".")
        return text if text else "0"

    def _extract_atom_sites(cif_contents):
        try:
            content_type, content_string = cif_contents.split(',')
            decoded = base64.b64decode(content_string).decode('utf-8', errors='ignore')
            parser = CifParser(io.StringIO(decoded))
            cif_dict = parser.as_dict()
            if not cif_dict:
                return []

            first_key = list(cif_dict.keys())[0]
            data = cif_dict[first_key]

            labels = data.get("_atom_site_label", [])
            types = data.get("_atom_site_type_symbol", [])
            xs = data.get("_atom_site_fract_x", [])
            ys = data.get("_atom_site_fract_y", [])
            zs = data.get("_atom_site_fract_z", [])
            occupancies = data.get("_atom_site_occupancy", [])

            labels = labels if isinstance(labels, list) else [labels]
            types = types if isinstance(types, list) else [types]
            xs = xs if isinstance(xs, list) else [xs]
            ys = ys if isinstance(ys, list) else [ys]
            zs = zs if isinstance(zs, list) else [zs]
            occupancies = occupancies if isinstance(occupancies, list) else [occupancies]

            site_count = min(len(labels), len(types), len(xs), len(ys), len(zs))
            sites = []
            for index in range(site_count):
                sites.append({
                    "label": _clean_cif_value(labels[index]),
                    "type_symbol": _clean_cif_value(types[index]),
                    "x": _as_float(xs[index]),
                    "y": _as_float(ys[index]),
                    "z": _as_float(zs[index]),
                    "occupancy": _as_float(occupancies[index] if index < len(occupancies) else 1, 1.0),
                })
            return sites
        except Exception as e:
            print("Error extracting atom sites:", e)
            return []

    def _build_pawley_content(xy_filename, cif_entries):
        lines = []
        lines.append("r_wp 0 r_exp 0 r_p 0 r_wp_dash 0 r_p_dash 0 r_exp_dash 0 weighted_Durbin_Watson 0 gof 0")
        lines.append("")
        lines.append("iters 100000")
        lines.append("chi2_convergence_criteria 0.001")
        lines.append("do_errors")
        lines.append("")
        lines.append(f"xdd {xy_filename}")
        lines.append("\tx_calculation_step = Yobs_dx_at(Xo); convolution_step 4")
        lines.append("\tbkg @ 0 0 0 0 0 0")
        lines.append("")
        lines.append("\tlam")
        lines.append("\t\tymin_on_ymax 0.0001")
        lines.append("\t\tla 0.653817 lo 1.540596  lh 0.501844")
        lines.append("\t\tla 0.346183 lo 1.544493  lh 0.626579")
        lines.append("")
        lines.append("\t'Zero_Error(zero,0)")
        lines.append("")

        lpa_index = 1
        for idx, entry in enumerate(cif_entries):
            suffix = "" if idx == 0 else str(idx)
            pku = f"pku{suffix}"
            pkv = f"pkv{suffix}"
            pkw = f"pkw{suffix}"
            pkx = f"pkx{suffix}"
            pky = f"pky{suffix}"
            pkz = f"pkz{suffix}"
            axial = f"axial{suffix}"

            a = entry["a"]
            b = entry["b"]
            c = entry["c"]
            al = entry["alpha"]
            be = entry["beta"]
            ga = entry["gamma"]
            phase_name = entry["phase_name"]
            space_group = entry["space_group"]

            ab_equal = _lpa_equal(a, b)
            ac_equal = _lpa_equal(a, c)
            bc_equal = _lpa_equal(b, c)
            lpa_tag = None
            if ab_equal or ac_equal or bc_equal:
                lpa_tag = f"lpa{lpa_index}"
                lpa_index += 1

            lines.append("\thkl_Is")
            lines.append(
                f"\t\tTCHZ_Peak_Type({pku}, 0.00039,{pkv}, -0.00221,{pkw}, -0.00146,!{pkx}, 0.0000,{pky}, 0.00957,!{pkz}, 0.0000)"
            )
            lines.append(f"\t\tSimple_Axial_Model(!{axial},10)")
            lines.append("")
            use_lpa_a = lpa_tag if (ab_equal or ac_equal) else None
            use_lpa_b = lpa_tag if (ab_equal or bc_equal) else None
            use_lpa_c = lpa_tag if (ac_equal or bc_equal) else None
            lines.append(_format_lattice_line_with_tag("a", a, use_lpa_a))
            lines.append(_format_lattice_line_with_tag("b", b, use_lpa_b))
            lines.append(_format_lattice_line_with_tag("c", c, use_lpa_c))
            lines.append(f"\t\tal {al:.6f}")
            lines.append(f"\t\tbe {be:.6f}")
            lines.append(f"\t\tga {ga:.6f}")
            lines.append(f"\t\tCreate_2Th_Ip_file({phase_name}-hkl)")
            lines.append(f"\t\tphase_name \"{phase_name}\"")
            lines.append(f"\t\tspace_group \"{space_group}\"")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_riet_content(xy_filename, cif_entries):
        lines = []
        lines.append("r_wp 0 r_exp 0 r_p 0 r_wp_dash 0 r_p_dash 0 r_exp_dash 0 weighted_Durbin_Watson 0 gof 0")
        lines.append("")
        lines.append("iters 100000")
        lines.append("chi2_convergence_criteria 0.001")
        lines.append("do_errors")
        lines.append("")
        lines.append(f"xdd {xy_filename}")
        lines.append("\tx_calculation_step = Yobs_dx_at(Xo); convolution_step 4")
        lines.append("\tbkg @ 0 0 0 0 0 0")
        lines.append("")
        lines.append("\tlam")
        lines.append("\t\tymin_on_ymax 0.0001")
        lines.append("\t\tla 0.653817 lo 1.540596  lh 0.501844")
        lines.append("\t\tla 0.346183 lo 1.544493  lh 0.626579")
        lines.append("")

        lpa_index = 1
        for idx, entry in enumerate(cif_entries):
            suffix = "" if idx == 0 else str(idx)
            pku = f"pku{suffix}"
            pkv = f"pkv{suffix}"
            pkw = f"pkw{suffix}"
            pkx = f"pkx{suffix}"
            pky = f"pky{suffix}"
            pkz = f"pkz{suffix}"
            axial = f"axial{suffix}"

            lines.append("\tstr")
            lines.append(f"\t\tphase_name \"{entry['phase_name']}\"")
            lines.append(f"\t\tal {entry['alpha']:.6f}")
            lines.append(f"\t\tbe {entry['beta']:.6f}")
            lines.append(f"\t\tga {entry['gamma']:.6f}")
            lines.append(f"\t\tvolume {entry['volume']:.1f}")

            a = entry["a"]
            b = entry["b"]
            c = entry["c"]
            ab_equal = _lpa_equal(a, b)
            ac_equal = _lpa_equal(a, c)
            bc_equal = _lpa_equal(b, c)
            lpa_tag = None
            if ab_equal or ac_equal or bc_equal:
                lpa_tag = f"lpa{lpa_index}"
                lpa_index += 1

            use_lpa_a = lpa_tag if (ab_equal or ac_equal) else None
            use_lpa_b = lpa_tag if (ab_equal or bc_equal) else None
            use_lpa_c = lpa_tag if (ac_equal or bc_equal) else None

            lines.append(_format_lattice_line_with_tag("a", a, use_lpa_a))
            lines.append(_format_lattice_line_with_tag("b", b, use_lpa_b))
            lines.append(_format_lattice_line_with_tag("c", c, use_lpa_c))

            for site in entry["sites"]:
                lines.append(
                    "\t\t\t"
                    f"site {site['label']}    x {_format_coord(site['x'])}       "
                    f"y {_format_coord(site['y'])}       z {_format_coord(site['z'])}        "
                    f"occ {site['type_symbol']}   {_format_coord(site['occupancy'])}"
                )

            lines.append("")
            lines.append("\t\tscale @ 0.0001")
            lines.append("\t\tr_bragg 0")
            lines.append(
                f"\t\tTCHZ_Peak_Type({pku}, 0.00039,{pkv}, -0.00221,{pkw}, -0.00146,!{pkx}, 0.0000,{pky}, 0.00957,!{pkz}, 0.0000)"
            )
            lines.append(f"\t\tSimple_Axial_Model({axial},10)")
            lines.append("\t\tPhase_Density_g_on_cm3(0)")
            lines.append(f"\t\tspace_group \"{entry['space_group']}\"")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    @app.callback(
        Output("pawley-content-store", "data"),
        Input("generate-pawley-btn", "n_clicks"),
        [State("upload-xy", "filename"),
         State("cif-store", "data"),
         State("cif-order-store", "data"),
         State("cif-visibility-store", "data"),
         State("lattice-1-a", "value"),
         State("lattice-2-a", "value"),
         State("lattice-3-a", "value"),
         State("lattice-4-a", "value"),
         State("lattice-5-a", "value"),
         State("lattice-6-a", "value"),
         State("lattice-1-b", "value"),
         State("lattice-2-b", "value"),
         State("lattice-3-b", "value"),
         State("lattice-4-b", "value"),
         State("lattice-5-b", "value"),
         State("lattice-6-b", "value"),
         State("lattice-1-c", "value"),
         State("lattice-2-c", "value"),
         State("lattice-3-c", "value"),
         State("lattice-4-c", "value"),
         State("lattice-5-c", "value"),
         State("lattice-6-c", "value"),
         State("lattice-1-alpha", "value"),
         State("lattice-2-alpha", "value"),
         State("lattice-3-alpha", "value"),
         State("lattice-4-alpha", "value"),
         State("lattice-5-alpha", "value"),
         State("lattice-6-alpha", "value"),
         State("lattice-1-beta", "value"),
         State("lattice-2-beta", "value"),
         State("lattice-3-beta", "value"),
         State("lattice-4-beta", "value"),
         State("lattice-5-beta", "value"),
         State("lattice-6-beta", "value"),
         State("lattice-1-gamma", "value"),
         State("lattice-2-gamma", "value"),
         State("lattice-3-gamma", "value"),
         State("lattice-4-gamma", "value"),
         State("lattice-5-gamma", "value"),
         State("lattice-6-gamma", "value")],
        prevent_initial_call=True
    )
    def generate_pawley_inp(n_clicks, xy_filename, cif_data, cif_order, visibility_state,
                            a1, a2, a3, a4, a5, a6,
                            b1, b2, b3, b4, b5, b6,
                            c1, c2, c3, c4, c5, c6,
                            alpha1, alpha2, alpha3, alpha4, alpha5, alpha6,
                            beta1, beta2, beta3, beta4, beta5, beta6,
                            gamma1, gamma2, gamma3, gamma4, gamma5, gamma6):
        if not n_clicks:
            return no_update

        file_names = cif_order if cif_order else []
        if not cif_data or len(file_names) == 0:
            return ""

        xy_name = xy_filename if xy_filename else "RENAME.xy"
        a_vals = [a1, a2, a3, a4, a5, a6]
        b_vals = [b1, b2, b3, b4, b5, b6]
        c_vals = [c1, c2, c3, c4, c5, c6]
        alpha_vals = [alpha1, alpha2, alpha3, alpha4, alpha5, alpha6]
        beta_vals = [beta1, beta2, beta3, beta4, beta5, beta6]
        gamma_vals = [gamma1, gamma2, gamma3, gamma4, gamma5, gamma6]

        cif_entries = []
        for i, file_name in enumerate(file_names):
            if visibility_state and file_name in visibility_state and not visibility_state[file_name]:
                continue
            if a_vals[i] is None or b_vals[i] is None or c_vals[i] is None:
                continue
            try:
                structure = parse_cif(cif_data[file_name])
                space_group = _extract_space_group(cif_data[file_name], structure)
            except Exception as e:
                print("Error parsing CIF for Pawley:", e)
                space_group = ""

            phase_name = file_name[:-4] if file_name.lower().endswith('.cif') else file_name
            cif_entries.append({
                "a": float(a_vals[i]),
                "b": float(b_vals[i]),
                "c": float(c_vals[i]),
                "alpha": float(alpha_vals[i]) if alpha_vals[i] is not None else 90.0,
                "beta": float(beta_vals[i]) if beta_vals[i] is not None else 90.0,
                "gamma": float(gamma_vals[i]) if gamma_vals[i] is not None else 90.0,
                "phase_name": phase_name,
                "space_group": space_group
            })

        content = _build_pawley_content(xy_name, cif_entries)
        # NOTE: unlike the web app, we don't also write pawley.inp to the current
        # working directory here — inside a packaged desktop app, cwd may not be
        # writable, and the content is already delivered via dcc.Download below.
        return content

    @app.callback(
        Output("riet-content-store", "data"),
        Input("generate-riet-btn", "n_clicks"),
        [State("upload-xy", "filename"),
         State("cif-store", "data"),
         State("cif-order-store", "data"),
         State("cif-visibility-store", "data"),
         State("lattice-1-a", "value"),
         State("lattice-2-a", "value"),
         State("lattice-3-a", "value"),
         State("lattice-4-a", "value"),
         State("lattice-5-a", "value"),
         State("lattice-6-a", "value"),
         State("lattice-1-b", "value"),
         State("lattice-2-b", "value"),
         State("lattice-3-b", "value"),
         State("lattice-4-b", "value"),
         State("lattice-5-b", "value"),
         State("lattice-6-b", "value"),
         State("lattice-1-c", "value"),
         State("lattice-2-c", "value"),
         State("lattice-3-c", "value"),
         State("lattice-4-c", "value"),
         State("lattice-5-c", "value"),
         State("lattice-6-c", "value"),
         State("lattice-1-alpha", "value"),
         State("lattice-2-alpha", "value"),
         State("lattice-3-alpha", "value"),
         State("lattice-4-alpha", "value"),
         State("lattice-5-alpha", "value"),
         State("lattice-6-alpha", "value"),
         State("lattice-1-beta", "value"),
         State("lattice-2-beta", "value"),
         State("lattice-3-beta", "value"),
         State("lattice-4-beta", "value"),
         State("lattice-5-beta", "value"),
         State("lattice-6-beta", "value"),
         State("lattice-1-gamma", "value"),
         State("lattice-2-gamma", "value"),
         State("lattice-3-gamma", "value"),
         State("lattice-4-gamma", "value"),
         State("lattice-5-gamma", "value"),
         State("lattice-6-gamma", "value")],
        prevent_initial_call=True
    )
    def generate_riet_inp(n_clicks, xy_filename, cif_data, cif_order, visibility_state,
                          a1, a2, a3, a4, a5, a6,
                          b1, b2, b3, b4, b5, b6,
                          c1, c2, c3, c4, c5, c6,
                          alpha1, alpha2, alpha3, alpha4, alpha5, alpha6,
                          beta1, beta2, beta3, beta4, beta5, beta6,
                          gamma1, gamma2, gamma3, gamma4, gamma5, gamma6):
        if not n_clicks:
            return no_update

        file_names = cif_order if cif_order else []
        if not cif_data or len(file_names) == 0:
            return ""

        xy_name = xy_filename if xy_filename else "RENAME.xy"

        a_vals = [a1, a2, a3, a4, a5, a6]
        b_vals = [b1, b2, b3, b4, b5, b6]
        c_vals = [c1, c2, c3, c4, c5, c6]
        alpha_vals = [alpha1, alpha2, alpha3, alpha4, alpha5, alpha6]
        beta_vals = [beta1, beta2, beta3, beta4, beta5, beta6]
        gamma_vals = [gamma1, gamma2, gamma3, gamma4, gamma5, gamma6]

        cif_entries = []
        for i, file_name in enumerate(file_names):
            if visibility_state and file_name in visibility_state and not visibility_state[file_name]:
                continue
            try:
                structure = parse_cif(cif_data[file_name])
                space_group = _extract_space_group(cif_data[file_name], structure)
                sites = _extract_atom_sites(cif_data[file_name])
            except Exception as e:
                print("Error parsing CIF for Riet:", e)
                continue

            if not sites:
                continue

            a_value = a_vals[i] if i < len(a_vals) and a_vals[i] is not None else structure.lattice.a
            b_value = b_vals[i] if i < len(b_vals) and b_vals[i] is not None else structure.lattice.b
            c_value = c_vals[i] if i < len(c_vals) and c_vals[i] is not None else structure.lattice.c
            alpha_value = alpha_vals[i] if i < len(alpha_vals) and alpha_vals[i] is not None else structure.lattice.alpha
            beta_value = beta_vals[i] if i < len(beta_vals) and beta_vals[i] is not None else structure.lattice.beta
            gamma_value = gamma_vals[i] if i < len(gamma_vals) and gamma_vals[i] is not None else structure.lattice.gamma
            edited_lattice = structure.lattice.from_parameters(
                float(a_value), float(b_value), float(c_value),
                float(alpha_value), float(beta_value), float(gamma_value)
            )

            phase_name = file_name[:-4] if file_name.lower().endswith('.cif') else file_name
            cif_entries.append({
                "a": float(a_value),
                "b": float(b_value),
                "c": float(c_value),
                "alpha": float(alpha_value),
                "beta": float(beta_value),
                "gamma": float(gamma_value),
                "volume": float(edited_lattice.volume),
                "phase_name": phase_name,
                "space_group": space_group,
                "sites": sites,
            })

        content = _build_riet_content(xy_name, cif_entries)
        # NOTE: see generate_pawley_inp above — no cwd write here either.
        return content

    @app.callback(
        Output("pawley-download", "data"),
        Input("pawley-content-store", "data"),
        State("upload-xy", "filename"),
        prevent_initial_call=True
    )
    def download_pawley_inp(content, xy_filename):
        if not content:
            return no_update

        download_name = "pawley.inp"
        if xy_filename:
            stem, ext = os.path.splitext(os.path.basename(xy_filename))
            if stem and ext.lower() == ".xy":
                download_name = f"{stem}_pawley.inp"

        return {
            "content": content,
            "filename": download_name,
            "type": "text/plain"
        }

    @app.callback(
        Output("riet-download", "data"),
        Input("riet-content-store", "data"),
        State("upload-xy", "filename"),
        prevent_initial_call=True
    )
    def download_riet_inp(content, xy_filename):
        if not content:
            return no_update

        download_name = "Riet.inp"
        if xy_filename:
            stem, ext = os.path.splitext(os.path.basename(xy_filename))
            if stem and ext.lower() == ".xy":
                download_name = f"{stem}_Riet.inp"

        return {
            "content": content,
            "filename": download_name,
            "type": "text/plain"
        }

    app.clientside_callback(
        """
        function(content) {
            if (!content) {
                return "";
            }
            if (navigator && navigator.clipboard) {
                navigator.clipboard.writeText(content);
                return "Copied!";
            }
            return "Copy failed";
        }
        """,
        Output("pawley-copy-status", "children"),
        Input("pawley-content-store", "data")
    )

    app.clientside_callback(
        """
        function(content) {
            if (!content) {
                return "";
            }
            if (navigator && navigator.clipboard) {
                navigator.clipboard.writeText(content);
                return "Copied!";
            }
            return "Copy failed";
        }
        """,
        Output("riet-copy-status", "children"),
        Input("riet-content-store", "data")
    )
