from dash import dcc, html

def create_file_control(index, filename):
    """
    Creates the layout for per-file controls.
    Removes the '.xy' extension (case insensitive) from the filename if it exists.
    The filename is rendered in a fixed-width container with text truncation.
    """
    corrected_filename = filename
    if corrected_filename.lower().endswith('.xy'):
        corrected_filename = corrected_filename[:-3]
    return html.Div([
        html.Div(
            corrected_filename,
            style={
                'display': 'inline-block',
                'width': '200px',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',
                'whiteSpace': 'nowrap',
                'fontWeight': '600',
                'fontSize': '13px'
            },
            title=corrected_filename
        ),
        html.Div("Level", className="field-label", style={'marginLeft': '14px', 'width': '46px'}),
        html.Div(
            dcc.Slider(
                id={'type': 'bg-slider', 'index': index},
                min=-10,
                max=50,
                step=0.5,
                value=0,
                updatemode="drag",
                marks={
                    -10: {'label': "-10", 'style': {'fontSize': '11px'}},
                     0:  {'label': "0",   'style': {'fontSize': '11px'}},
                     50: {'label': "50",  'style': {'fontSize': '11px'}}
                },
                tooltip={"placement": "bottom", "always_visible": True}
            ),
            style={'display': 'inline-block', 'marginLeft': '8px', 'width': '28%'}
        ),
        html.Div("Intensity", className="field-label", style={'marginLeft': '14px', 'width': '62px'}),
        html.Div(
            dcc.Slider(
                id={'type': 'int-slider', 'index': index},
                min=1,
                max=200,
                step=1,
                value=100,
                updatemode="drag",
                marks={
                    1:   {'label': "1",   'style': {'fontSize': '11px'}},
                    100: {'label': "100", 'style': {'fontSize': '11px'}},
                    200: {'label': "200", 'style': {'fontSize': '11px'}}
                },
                tooltip={"placement": "bottom", "always_visible": True}
            ),
            style={'display': 'inline-block', 'marginLeft': '8px', 'width': '28%'}
        ),
        html.Div(
            [
                html.Button(
                    "↑",
                    id={'type': 'move-up-button', 'index': index},
                    n_clicks=0,
                    title='Move up in legend',
                    className="btn btn-neutral",
                    style={'width': '32px', 'height': '32px', 'padding': '0', 'marginLeft': '12px'}
                ),
                html.Button(
                    "↓",
                    id={'type': 'move-down-button', 'index': index},
                    n_clicks=0,
                    title='Move down in legend',
                    className="btn btn-neutral",
                    style={'width': '32px', 'height': '32px', 'padding': '0', 'marginLeft': '6px'}
                )
            ],
            style={'display': 'flex', 'alignItems': 'center'}
        )
    ], className="panel-row", style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px'})

def create_layout(app):
    # Upload component for drag & drop .xy files with a light grey background.
    upload_component = dcc.Upload(
        id="upload-data",
        accept=".xy",
        children=html.Div(
            "Drop .xy file(s) here or Click to upload",
            style={'width': '100%', 'textAlign': 'center', 'fontSize': '14px'}
        ),
        className="upload-zone",
        style={
            'width': '90%',
            'height': '56px',
            'lineHeight': '56px',
            'margin': '10px auto',
            'display': 'flex',
            'justifyContent': 'center',
            'alignItems': 'center'
        },
        multiple=True
    )

    # Store to hold the current file list.
    file_store = dcc.Store(id="file-store", data=[])

    # Store to track whether legend is shown (True) or hidden (False). Defaults to True.
    legend_store = dcc.Store(id="legend-store", data=True)

    # Ratio controls placed above the angle sliders.
    ratio_controls = html.Div([
        html.Div([
            html.Div("Width", className="field-label", style={'marginRight': '10px', 'display': 'inline-block'}),
            dcc.Input(
                id='width-ratio-input',
                type='number',
                placeholder='e.g., 4',
                value=4,
                debounce=True,
                className="field-input",
                style={
                    'width': '70px',
                    'height': '30px',
                    'fontSize': '14px'
                }
            )
        ], style={'display': 'inline-block', 'marginRight': '20px'}),
        html.Div([
            html.Div("Height", className="field-label", style={'marginRight': '10px', 'display': 'inline-block'}),
            dcc.Input(
                id='height-ratio-input',
                type='number',
                placeholder='e.g., 3',
                value=3,
                debounce=True,
                className="field-input",
                style={
                    'width': '70px',
                    'height': '30px',
                    'fontSize': '14px'
                }
            )
        ], style={'display': 'inline-block'}),
    ], className="panel-row", style={'margin': '16px 10px', 'textAlign': 'center'})

    # Global slider controls.
    angle_marks = {i: {'label': str(i), 'style': {'fontSize': '11px'}} for i in range(0, 101, 10)}

    global_controls = html.Div([
        html.Div([
            html.Div("Angle Range", className="field-label", style={'marginBottom': '6px'}),
            dcc.RangeSlider(
                id='angle-range-slider',
                min=0,
                max=100,
                step=1,
                value=[10, 90],  # Default range
                marks=angle_marks,
                tooltip={"placement": "bottom", "always_visible": True}
            )
        ], style={'margin': '16px', 'width': '90%'}),
        html.Div([
            html.Div("Global Separation", className="field-label", style={'marginBottom': '6px'}),
            dcc.Slider(
                id='global-sep-slider',
                min=0,
                max=150,
                step=1,
                value=0,
                updatemode="drag",
                marks={i: {'label': str(i), 'style': {'fontSize': '11px'}} for i in range(0, 151, 10)},
                tooltip={"placement": "bottom", "always_visible": True}
            )
        ], style={'margin': '16px', 'width': '90%'})
    ])

    # Container for per-file controls.
    per_file_controls_container = html.Div([
        html.Div(id="per-file-controls-section", style={'padding': '10px'})
    ])

    # Buttons and download component.
    reset_button = html.Button(
        "Reset",
        id="reset-button",
        n_clicks=0,
        className="btn btn-neutral",
        style={'padding': '10px 18px'}
    )

    # NEW LEGEND BUTTON
    legend_button = html.Button(
        "Legend",
        id="legend-button",
        n_clicks=0,
        className="btn btn-neutral",
        style={'padding': '10px 18px', 'marginLeft': '8px'}
    )

    save_white_button = html.Button(
        "Save Plot (White)",
        id="save-white-button",
        n_clicks=0,
        className="btn btn-accent",
        style={'padding': '10px 18px'}
    )
    save_transparent_button = html.Button(
        "Save Plot (Transparent)",
        id="save-transparent-button",
        n_clicks=0,
        className="btn btn-accent",
        style={'padding': '10px 18px'}
    )
    download_component = dcc.Download(id="download")

    # Arrange Reset, Legend, and Save buttons on the same horizontal line.
    button_row = html.Div(
        [
            reset_button,
            legend_button,  # <--- The new Legend button is placed here
            html.Div(
                [
                    save_white_button,
                    save_transparent_button
                ],
                style={'display': 'flex', 'gap': '8px', 'marginLeft': '20px'}
            )
        ],
        style={'display': 'flex', 'alignItems': 'center', 'margin': '10px'}
    )

    # Graph container holds the graph.
    graph_container = html.Div(
        [
            html.Div(
                dcc.Graph(
                    id='graph',
                    config={'displayModeBar': True, 'doubleClick': 'reset'},
                    style={'position': 'absolute', 'top': 0, 'left': 0, 'right': 0, 'bottom': 0}
                ),
                className="panel",
                style={
                    'position': 'relative',
                    'width': '100%',
                    'paddingBottom': '75%'  # Default 4:3 ratio
                },
                id='graph-wrapper'
            )
        ],
        style={
            'width': '50%',
            'position': 'relative',
            'padding': '5px'
        }
    )

    # Controls container (takes up the other 50% of the window width).
    controls_container = html.Div(
        [
            button_row,
            download_component,
            ratio_controls,
            global_controls,
            html.Hr(style={'border': 'none', 'borderTop': '1px solid #e3e5eb', 'margin': '16px 0'}),
            per_file_controls_container,
            upload_component
        ],
        style={'width': '50%', 'paddingLeft': '16px'}
    )

    # Main layout: file store, legend store, and a two-column layout for graph and controls.
    layout = html.Div([
        file_store,
        legend_store,  # <--- Add the legend store here
        html.Div([graph_container, controls_container],
                 style={'display': 'flex', 'flexDirection': 'row', 'width': '100%'})
    ],
    style={'font-family': 'Dejavu Sans', 'fontSize': '14px'}
    )

    return layout