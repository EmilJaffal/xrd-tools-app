import dash
import plotly.graph_objects as go
from dash import dcc, Input, Output, State, ALL, callback_context
import plotly.io as pio
import numpy as np
import io
from dash import html
import re
import json

from .utils import generate_figure, parse_contents
from .layout import create_file_control

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

def register_callbacks(app):
    # Callback: Update the file store when files are uploaded.
    @app.callback(
        Output("file-store", "data"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        State("file-store", "data")
    )
    def update_file_store(upload_contents, upload_filenames, current_files):
        current_files = current_files or []
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
        return [create_file_control(i, file["filename"]) for i, file in enumerate(files)]

    @app.callback(
        Output("file-store", "data", allow_duplicate=True),
        Output({'type': 'bg-slider', 'index': ALL}, 'value', allow_duplicate=True),
        Output({'type': 'int-slider', 'index': ALL}, 'value', allow_duplicate=True),
        Input({'type': 'move-up-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'move-down-button', 'index': ALL}, 'n_clicks'),
        State("file-store", "data"),
        State({'type': 'bg-slider', 'index': ALL}, 'value'),
        State({'type': 'int-slider', 'index': ALL}, 'value'),
        prevent_initial_call=True
    )
    def reorder_files_for_legend(up_clicks, down_clicks, files, bg_values, int_values):
        if not files:
            raise dash.exceptions.PreventUpdate

        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        triggered_prop = ctx.triggered[0].get('prop_id', '')
        triggered_id_part = triggered_prop.split('.')[0] if triggered_prop else ''
        try:
            triggered_id = json.loads(triggered_id_part)
        except Exception:
            triggered_id = None

        if not isinstance(triggered_id, dict):
            raise dash.exceptions.PreventUpdate

        idx = triggered_id.get('index')
        button_type = triggered_id.get('type')
        if idx is None or button_type not in ('move-up-button', 'move-down-button'):
            raise dash.exceptions.PreventUpdate

        if idx < 0 or idx >= len(files):
            raise dash.exceptions.PreventUpdate

        if not bg_values or len(bg_values) != len(files):
            bg_values = [0] * len(files)
        if not int_values or len(int_values) != len(files):
            int_values = [100] * len(files)

        target_idx = idx - 1 if button_type == 'move-up-button' else idx + 1
        if target_idx < 0 or target_idx >= len(files):
            raise dash.exceptions.PreventUpdate

        reordered_files = files.copy()
        reordered_bg = bg_values.copy()
        reordered_int = int_values.copy()

        reordered_files[idx], reordered_files[target_idx] = reordered_files[target_idx], reordered_files[idx]
        reordered_bg[idx], reordered_bg[target_idx] = reordered_bg[target_idx], reordered_bg[idx]
        reordered_int[idx], reordered_int[target_idx] = reordered_int[target_idx], reordered_int[idx]

        return reordered_files, reordered_bg, reordered_int

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
        # Ensure slider values lists match the number of files.
        if not bg_values or len(bg_values) != len(files):
            bg_values = [0] * len(files)
        if not int_values or len(int_values) != len(files):
            int_values = [100] * len(files)

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

    # Callback: Reset global separation and per-file controls.
    @app.callback(
        Output('global-sep-slider', 'value'),
        Output({'type': 'bg-slider', 'index': ALL}, 'value'),
        Output({'type': 'int-slider', 'index': ALL}, 'value'),
        Input('reset-button', 'n_clicks'),
        State('file-store', 'data')
    )
    def reset_controls(n_clicks, files):
        if not n_clicks or n_clicks == 0:
            raise dash.exceptions.PreventUpdate
        num_files = len(files) if files else 0
        bg_defaults = [0] * num_files
        int_defaults = [100] * num_files
        return 0, bg_defaults, int_defaults

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
        Output("download", "data"),
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
            print("No files available")
            return dash.no_update

        angle_min, angle_max = angle_range
        print(f"Angle range: {angle_min} - {angle_max}")

        # Generate the figure
        fig = generate_figure(angle_min, angle_max, global_sep, bg_values, int_values, files)
        print(f"Generated figure: {fig}")

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
            raise dash.exceptions.PreventUpdate

        def write_bytes(bytes_io):
            bytes_io.write(img_bytes)

        # Set filename
        if trigger.startswith("save-white-button"):
            filename = "plot_white.png"
        else:
            filename = "plot_transparent.png"

        print(f"Saving file: {filename}")
        return dcc.send_bytes(write_bytes, filename)