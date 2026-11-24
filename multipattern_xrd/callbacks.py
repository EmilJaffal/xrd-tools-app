import dash
import plotly.graph_objects as go
from dash import Input, Output, State, ALL, callback_context
import plotly.io as pio
import numpy as np
import io
from dash import html
import re
import json
from pathlib import Path

from .utils import generate_figure, parse_contents
from .layout import create_file_control, create_upload_component

Y_AXIS_DOMAIN_75 = [0.125, 0.875]


def extract_sort_value(filename):
    """Return numeric sort key from filename; non-numeric names sort last."""
    ta_match = re.search(r'Ta([0-9]+(?:\.[0-9]+)?)', filename)
    if ta_match:
        return float(ta_match.group(1))
    generic_match = re.search(r'([0-9]+(?:\.[0-9]+)?)', filename)
    if generic_match:
        return float(generic_match.group(1))
    return float('inf')

def compute_default_angles(files):
    """
    Computes the default min and max angles from the uploaded files.
    Reads the first column from each file (parsed as a string) using np.genfromtxt.
    """
    all_angles = []
    for file in files:
        try:
            data = np.genfromtxt(io.StringIO(file["content"]))
            if data.ndim < 2 or data.shape[1] < 2:
                continue
            angles = data[:, 0]
            all_angles.extend(angles)
        except Exception:
            continue
    if all_angles:
        return float(min(all_angles)), float(max(all_angles))
    return 10, 90  # Fallback defaults if no valid data is found.

def snapshot_settings(files, bg_values, int_values):
    """Copy each file entry with its current Level/Intensity slider values
    stored on it ("bg"/"int"). The per-file controls are rebuilt from the file
    store whenever files are added, removed or reordered, so without this every
    pattern would snap back to the defaults on each of those actions."""
    files = [dict(f) for f in (files or [])]
    if bg_values and len(bg_values) == len(files):
        for f, v in zip(files, bg_values):
            f["bg"] = v
    if int_values and len(int_values) == len(files):
        for f, v in zip(files, int_values):
            f["int"] = v
    return files


def slider_values(files, bg_values, int_values, prefer_stored=False):
    """Level/Intensity per file for plotting. Falls back to the values stored
    on the file entries when the live sliders don't line up with the files —
    i.e. the store just changed and the controls haven't been rebuilt yet."""
    if prefer_stored or not bg_values or len(bg_values) != len(files):
        bg_values = [f.get("bg", 0) for f in files]
    if prefer_stored or not int_values or len(int_values) != len(files):
        int_values = [f.get("int", 100) for f in files]
    return bg_values, int_values


def unique_download_path(filename):
    """~/Downloads/<filename>, adding " (1)", " (2)", ... instead of
    overwriting an earlier plot — the same way a browser download would."""
    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(filename).stem, Path(filename).suffix
    path = downloads_dir / filename
    n = 1
    while path.exists():
        path = downloads_dir / f"{stem} ({n}){suffix}"
        n += 1
    return path


def triggered_click(ctx, button_types):
    """(index, type) of the pattern-matched button that was actually clicked,
    or None. Rebuilding the per-file controls mounts fresh buttons with
    n_clicks=0, which Dash also reports as a trigger — those must be ignored,
    or e.g. adding a file would act like clicking the first row's buttons."""
    if not ctx.triggered:
        return None
    trig = ctx.triggered[0]
    if not trig.get('value'):
        return None
    try:
        triggered_id = json.loads(trig.get('prop_id', '').split('.')[0])
    except Exception:
        return None
    if not isinstance(triggered_id, dict) or triggered_id.get('type') not in button_types:
        return None
    return triggered_id.get('index'), triggered_id.get('type')


def register_callbacks(app):
    # Callback: Update the file store when files are uploaded.
    @app.callback(
        Output("file-store", "data"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        State("file-store", "data"),
        State({'type': 'bg-slider', 'index': ALL}, 'value'),
        State({'type': 'int-slider', 'index': ALL}, 'value'),
    )
    def update_file_store(upload_contents, upload_filenames, current_files, bg_values, int_values):
        # Reset swaps in a fresh upload component (contents=None), which
        # re-fires this callback — nothing was uploaded, so leave the store alone.
        if upload_contents is None:
            raise dash.exceptions.PreventUpdate
        current_files = snapshot_settings(current_files, bg_values, int_values)
        if upload_contents is not None:
            # Normalize to list.
            if not isinstance(upload_contents, list):
                upload_contents = [upload_contents]
                upload_filenames = [upload_filenames]
            new_files = []
            for contents, fname in zip(upload_contents, upload_filenames):
                if not fname or not fname.lower().endswith('.xy'):
                    continue
                new_files.append({"filename": fname, "content": parse_contents(contents)})
            current_files.extend(new_files)
            def legend_sort_key(file_entry):
                value = extract_sort_value(file_entry["filename"])
                if value == float('inf'):
                    return (1, 0.0)
                return (0, -value)

            current_files = sorted(current_files, key=legend_sort_key)
        return current_files

    # Callback: Update per-file controls based on current files.
    @app.callback(
        Output("per-file-controls-section", "children"),
        Input("file-store", "data")
    )
    def update_per_file_controls(files):
        if not files:
            return []
        return [
            create_file_control(i, file["filename"], file.get("bg", 0), file.get("int", 100))
            for i, file in enumerate(files)
        ]

    # Callback: Move a pattern up/down (legend + stacking order) or remove it.
    @app.callback(
        Output("file-store", "data", allow_duplicate=True),
        Input({'type': 'move-up-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'move-down-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'remove-button', 'index': ALL}, 'n_clicks'),
        State("file-store", "data"),
        State({'type': 'bg-slider', 'index': ALL}, 'value'),
        State({'type': 'int-slider', 'index': ALL}, 'value'),
        prevent_initial_call=True
    )
    def reorder_or_remove_file(up_clicks, down_clicks, remove_clicks, files, bg_values, int_values):
        clicked = triggered_click(
            callback_context, ('move-up-button', 'move-down-button', 'remove-button'))
        if not files or clicked is None:
            raise dash.exceptions.PreventUpdate
        idx, button_type = clicked
        if idx is None or idx < 0 or idx >= len(files):
            raise dash.exceptions.PreventUpdate

        files = snapshot_settings(files, bg_values, int_values)

        if button_type == 'remove-button':
            del files[idx]
            return files

        target_idx = idx - 1 if button_type == 'move-up-button' else idx + 1
        if target_idx < 0 or target_idx >= len(files):
            raise dash.exceptions.PreventUpdate
        files[idx], files[target_idx] = files[target_idx], files[idx]
        return files

    # Callback: Toggle the legend store (flip True/False) when legend button is clicked.
    @app.callback(
        Output("legend-store", "data"),
        Input("legend-button", "n_clicks"),
        State("legend-store", "data"),
        prevent_initial_call=True
    )
    def toggle_legend(n_clicks, show_legend):
        return not show_legend

    # Callback: Update the graph based on slider inputs, files, and legend visibility.
    @app.callback(
        Output('graph', 'figure'),
        Input('angle-range-slider', 'value'),  # Updated to use the range slider
        Input('global-sep-slider', 'value'),
        Input({'type': 'bg-slider', 'index': ALL}, 'value'),
        Input({'type': 'int-slider', 'index': ALL}, 'value'),
        Input('file-store', 'data'),
        Input('legend-store', 'data')  # Legend visibility
    )
    def update_graph(angle_range, global_sep, bg_values, int_values, files, show_legend):
        if not files:
            return go.Figure()
        # When the file store itself changed (add/remove/reorder), the live
        # sliders still belong to the previous file list — plot with the
        # settings stored on each file until the controls are rebuilt.
        file_store_changed = any(
            t['prop_id'].startswith('file-store') for t in callback_context.triggered)
        bg_values, int_values = slider_values(
            files, bg_values, int_values, prefer_stored=file_store_changed)

        angle_min, angle_max = angle_range  # Extract min and max from the range slider
        fig = generate_figure(angle_min, angle_max, global_sep, bg_values, int_values, files)
        # Apply the legend visibility:
        fig.update_layout(
            legend=dict(
                font=dict(family="Dejavu Sans", size=20),
                yanchor='top',
                xanchor='left',
                x=1.02,
                y=Y_AXIS_DOMAIN_75[1],
                traceorder='normal'
            ),
            showlegend=show_legend
        )
        fig.update_yaxes(domain=Y_AXIS_DOMAIN_75)
        return fig

    # Combined Callback: Update angle range slider from file-store changes, reset-button, or graph relayout.
    @app.callback(
        Output('angle-range-slider', 'value'),  # Updated to use the range slider
        Input('file-store', 'data'),
        Input('graph', 'relayoutData'),
        Input('reset-button', 'n_clicks'),
        State('angle-range-slider', 'value')  # Updated to use the range slider
    )
    def update_angle_range_slider(files, relayoutData, n_clicks, current_range):
        ctx = callback_context
        if not ctx.triggered:
            return current_range

        trigger = ctx.triggered[0]['prop_id']
        # If file-store was updated or reset is clicked, update to computed defaults.
        if trigger.startswith("file-store") or trigger.startswith("reset-button"):
            if files:
                new_min, new_max = compute_default_angles(files)
                return [new_min, new_max]
            return [10, 90]

        # If the graph relayout triggered this callback.
        if trigger.startswith("graph"):
            if relayoutData:
                if 'xaxis.autorange' in relayoutData:
                    if files:
                        new_min, new_max = compute_default_angles(files)
                        return [new_min, new_max]
                    return [10, 90]
                if 'xaxis.range[0]' in relayoutData and 'xaxis.range[1]' in relayoutData:
                    try:
                        new_min = float(relayoutData['xaxis.range[0]'])
                        new_max = float(relayoutData['xaxis.range[1]'])
                        return [new_min, new_max]
                    except Exception:
                        pass
            return current_range

        return current_range

    # Callback: Reset the whole tab back to its initial state.
    # In the desktop window there's no page refresh to start over with, so Reset
    # has to clear the loaded patterns too — not just the slider values. Clearing
    # file-store removes the per-file controls (they're rebuilt with defaults on
    # the next upload) and re-fires update_angle_range_slider. The upload
    # component is swapped for a fresh one so its hidden file input forgets the
    # previous selection — otherwise re-picking the same files fires nothing.
    @app.callback(
        Output('file-store', 'data', allow_duplicate=True),
        Output('upload-wrapper', 'children'),
        Output('global-sep-slider', 'value'),
        Output('legend-store', 'data', allow_duplicate=True),
        Output('width-ratio-input', 'value'),
        Output('height-ratio-input', 'value'),
        Input('reset-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def reset_controls(n_clicks):
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        return [], create_upload_component(n_clicks), 0, True, 4, 3

    # Callback: Update the aspect ratio of the graph container.
    @app.callback(
        Output('graph-wrapper', 'style'),
        Input('width-ratio-input', 'value'),
        Input('height-ratio-input', 'value'),
        prevent_initial_call=True
    )
    def update_aspect_ratio(width_ratio, height_ratio):
        try:
            w = float(width_ratio)
            h = float(height_ratio)
            padding_bottom = f"{(h / w) * 100}%"
            return {'position': 'relative', 'width': '100%', 'paddingBottom': padding_bottom}
        except Exception:
            return {'position': 'relative', 'width': '100%', 'paddingBottom': '75%'}

    # Callback: Save the current plot in high resolution using the selected ratio.
    @app.callback(
        Output("save-status", "children"),
        Input("save-white-button", "n_clicks"),
        Input("save-transparent-button", "n_clicks"),
        State('angle-range-slider', 'value'),
        State('global-sep-slider', 'value'),
        State({'type': 'bg-slider', 'index': ALL}, 'value'),
        State({'type': 'int-slider', 'index': ALL}, 'value'),
        State('file-store', 'data'),
        State('width-ratio-input', 'value'),
        State('height-ratio-input', 'value'),
        State('legend-store', 'data'),
        prevent_initial_call=True
    )
    def save_plot(n_white, n_transparent, angle_range, global_sep,
                  bg_values, int_values, files, width_ratio, height_ratio, show_legend):
        print("Save plot callback triggered")
        ctx = callback_context
        if not ctx.triggered:
            print("No trigger detected")
            raise dash.exceptions.PreventUpdate
        trigger = ctx.triggered[0]['prop_id']
        print(f"Triggered by: {trigger}")

        if not files:
            return "✗ nothing to save yet"
        bg_values, int_values = slider_values(files, bg_values, int_values)

        angle_min, angle_max = angle_range
        print(f"Angle range: {angle_min} - {angle_max}")

        # Generate the figure
        fig = generate_figure(angle_min, angle_max, global_sep, bg_values, int_values, files)

        # Set background based on button clicked
        if trigger.startswith("save-transparent-button"):
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )

        # Apply font and legend visibility
        fig.update_layout(
            font=dict(family="Microsoft Sans Serif", size=18, color="black"),  # Apply font globally
            legend=dict(
                font=dict(family="Microsoft Sans Serif", size=18),
                yanchor='top',
                xanchor='left',
                x=1.02,
                y=Y_AXIS_DOMAIN_75[1],
                traceorder='normal'
            ),
            title=dict(
                font=dict(family="Microsoft Sans Serif", size=18)
            ),
            xaxis=dict(
                title=dict(font=dict(family="Microsoft Sans Serif", size=18)),
                tickfont=dict(family="Microsoft Sans Serif", size=18)
            ),
            yaxis=dict(
                title=dict(font=dict(family="Microsoft Sans Serif", size=18)),
                tickfont=dict(family="Microsoft Sans Serif", size=18)
            ),
            showlegend=show_legend
        )
        fig.update_yaxes(domain=Y_AXIS_DOMAIN_75)

        # Generate image bytes
        try:
            w_ratio = float(width_ratio)
            h_ratio = float(height_ratio)
            height = int(800 * (h_ratio / w_ratio))
        except Exception:
            height = 600

        # Some hosted environments are stricter on resources/headless rendering.
        # Try high quality first, then progressively lower quality to avoid hard failures.
        export_attempts = [
            {"width": 800, "height": height, "scale": 4},
            {"width": 800, "height": height, "scale": 2},
            {"width": 700, "height": max(500, int(height * 0.9)), "scale": 2},
            {"width": 700, "height": max(500, int(height * 0.9)), "scale": 1},
        ]

        img_bytes = None
        last_error = None
        for opts in export_attempts:
            try:
                img_bytes = pio.to_image(
                    fig,
                    format='png',
                    width=opts["width"],
                    height=opts["height"],
                    scale=opts["scale"],
                    engine='kaleido'
                )
                break
            except Exception as e:
                last_error = e
                print(f"Image export failed with options {opts}: {e}")

        if img_bytes is None:
            print(f"Error generating image after all fallbacks: {last_error}")
            return "✗ couldn't save plot"

        filename = ("multipattern_white.png" if trigger.startswith("save-white-button")
                    else "multipattern_transparent.png")
        # Write straight to ~/Downloads server-side, like XRD Match's plot
        # save, instead of a dcc.Download: in the desktop window that goes
        # through WKWebView's download handling and pops a native save panel
        # every time. A direct write behaves the same in dev and packaged.
        try:
            path = unique_download_path(filename)
            path.write_bytes(img_bytes)
        except Exception as e:
            print(f"Error saving plot: {e}")
            return "✗ couldn't save plot"
        print(f"Saved plot to {path}")
        return f"✓ Saved {path.name} to Downloads"