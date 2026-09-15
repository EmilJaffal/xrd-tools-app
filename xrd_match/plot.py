import math
import re
import plotly.graph_objects as go
import plotly.io as pio

# "Microsoft Sans Serif" (the previous setting here) isn't installed on
# macOS/Linux, so the browser silently substituted some other font for every
# label on the plot — inconsistent with the rest of the app's typography and,
# at these large point sizes, prone to looking heavy/uneven ("scrappy bold").
# "App Sans" is the same bundled Open Sans face declared via @font-face in
# assets/theme.css for the rest of the UI; the rest of the stack is a normal
# native-sans fallback in case that hasn't loaded yet.
PLOT_FONT_FAMILY = "App Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"


def _subscript_formula_html(text):
    """Wrap digit runs in <sub> so a phase name that's a chemical formula
    (e.g. "Fe2O3", from a CIF typically named after its compound) reads as
    Fe<sub>2</sub>O<sub>3</sub> instead of a plain "Fe2O3". Plotly annotation
    text supports this small HTML-like tag subset natively."""
    if not text:
        return text
    return "".join(
        f"<sub>{part}</sub>" if part.isdigit() else part
        for part in re.split(r"(\d+)", text)
    )


def plot_xrd(patterns, titles, wavelength, experimental_data=None, opacity=0.9, exp_filename=None, intensity_values=None):
    """
    Generate a Plotly figure of XRD patterns.
    """
    
    def extract_xy(pattern):
        try:
            return pattern.x, pattern.y
        except AttributeError:
            x_vals = [row[0] for row in pattern]
            y_vals = [row[1] for row in pattern]
            return x_vals, y_vals

    fig = go.Figure()

    # Determine the x-axis range.
    if experimental_data is not None:
        x_min = experimental_data['2_theta'].min()
        x_max = experimental_data['2_theta'].max()
        fig.add_trace(go.Scatter(
            x=experimental_data['2_theta'], 
            y=experimental_data['intensity'],
            mode='lines', 
            name=exp_filename if exp_filename else 'Experimental data',
            line=dict(color='black', width=1),
            showlegend=False
        ))
    else:
        x_min = min(min(extract_xy(pattern)[0]) for pattern in patterns)
        x_max = max(max(extract_xy(pattern)[0]) for pattern in patterns)

    for pattern, title in zip(patterns, titles):
        x_vals, y_vals = extract_xy(pattern)
        valid_indices = [i for i, x_val in enumerate(x_vals) if x_min <= x_val <= x_max]
        fig.add_trace(go.Bar(
            x=[x_vals[i] for i in valid_indices],
            y=[y_vals[i] for i in valid_indices],
            name=title,
            width=0.275,
            opacity=opacity,
            showlegend=False
        ))

    x_lower = int(math.floor(x_min))
    x_upper = int(math.ceil(x_max))
    big_ticks = [x for x in range(x_lower, x_upper + 1) if x % 10 == 0]

    tick_shapes = []
    for x in range(x_lower, x_upper + 1):
        if x % 10 == 0:
            tick_length = 0.04
            tick_color = 'black'
            tick_width = 2
        elif x % 5 == 0:
            tick_length = 0.03
            tick_color = 'grey'
            tick_width = 1.5
        else:
            tick_length = 0.02
            tick_color = 'grey'
            tick_width = 1
        tick_shapes.append(
            dict(
                type="line",
                xref="x", yref="paper",
                x0=x, x1=x,
                y0=0, y1=tick_length,
                line=dict(color=tick_color, width=tick_width)
            )
        )

    # Apply the app-wide font consistently across the whole figure.
    fig.update_layout(
        title=dict(
            text=f"",
            font=dict(family=PLOT_FONT_FAMILY, size=30, color="black")
        ),
        font=dict(family=PLOT_FONT_FAMILY, size=24, color="black"),
        # No explicit width/height here + autosize=True (paired with
        # dcc.Graph's responsive config in layout.py) so the plot actually
        # stretches to fill its container instead of Plotly's fixed ~700px
        # default — that default is what made the graph look "narrow" even
        # though its container was wide.
        autosize=True,
        xaxis=dict(
            title=dict(text="diffraction angle, 2<i>θ</i>", font=dict(family=PLOT_FONT_FAMILY, size=24)),
            range=[x_min, x_max],
            tickmode='array',
            tickvals=big_ticks,
            ticktext=[str(t) for t in big_ticks],
            ticks="",
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text="intensity, a.u.", font=dict(family=PLOT_FONT_FAMILY, size=24)),
            range=[0, 105],
            showgrid=False,
            tickfont=dict(family=PLOT_FONT_FAMILY, size=24)
        ),
        shapes=tick_shapes,
        template="plotly_white",
        barmode='overlay',
        plot_bgcolor='white',
        legend=dict(borderwidth=0)
    )
    
    # Add phase composition annotation if intensity values are provided
    if intensity_values and len(intensity_values) > 0 and len(titles) > 0:
        # Calculate total intensity
        total_intensity = sum(intensity_values)
        
        if total_intensity > 0:
            # Build composition text
            composition_lines = []
            
            # Get the default plotly color sequence
            plotly_colors = [
                '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
                '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
            ]
            
            # Add experimental data line if present
            if experimental_data is not None and exp_filename:
                composition_lines.append(
                    f'<span style="color:black">—</span> {exp_filename}'
                )
            
            for i, (title, intensity) in enumerate(zip(titles, intensity_values)):
                percentage = (intensity / total_intensity) * 100
                # Get color - offset by 1 if experimental data is present (black trace comes first)
                color_idx = i + 1 if experimental_data is not None else i
                color = plotly_colors[color_idx % len(plotly_colors)]
                # Strip .cif extension from title
                clean_title = title.replace('.cif', '') if title.endswith('.cif') else title
                composition_lines.append(
                    f'<span style="color:{color}">■</span> {_subscript_formula_html(clean_title)}: {percentage:.1f}%'
                )
            
            composition_text = "<br>".join(composition_lines)
            
            # Add annotation in top right
            fig.add_annotation(
                text=composition_text,
                xref="paper", yref="paper",
                x=0.98, y=0.98,
                xanchor="right", yanchor="top",
                showarrow=False,
                font=dict(family=PLOT_FONT_FAMILY, size=18, color="black"),
                bgcolor="rgba(255, 255, 255, 0.8)",
                borderwidth=0,
                borderpad=8,
                align="left"
            )
    
    return fig