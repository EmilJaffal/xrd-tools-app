import io
import numpy as np
import plotly.graph_objects as go
from scipy.ndimage import gaussian_filter1d
import base64

def generate_figure(angle_min, angle_max, global_sep, bg_values, int_values, files):
    sigma = 0.1  # smoothing parameter
    fig = go.Figure()
    
    for idx, file in enumerate(files):
        name = file["filename"]
        # Remove .xy extension (case insensitive) from the legend label.
        if name.lower().endswith('.xy'):
            name = name[:-3]
            
        try:
            data = np.genfromtxt(io.StringIO(file["content"]))
        except Exception:
            continue
        
        if data.ndim < 2 or data.shape[1] < 2:
            continue
        
        x = data[:, 0]
        y = data[:, 1]
        
        # Filter data by the current angle range.
        mask = (x >= angle_min) & (x <= angle_max)
        x_filtered = x[mask]
        y_filtered = y[mask]
        
        # Apply Gaussian smoothing.
        y_smoothed = gaussian_filter1d(y_filtered, sigma=sigma)
        
        bg = bg_values[idx] if idx < len(bg_values) else 0
        intensity = int_values[idx] if idx < len(int_values) else 100
        
        # Normalize and scale the data.
        y_min = np.min(y_smoothed)
        y_max = np.max(y_smoothed)
        if y_max - y_min == 0:
            y_normalized = y_smoothed - y_min
        else: 
            y_normalized = (y_smoothed - y_min) / (y_max - y_min)
        y_scaled = y_normalized * intensity
        
        # Keep graph stacking direction aligned with legend order.
        final_y = y_scaled + bg + ((len(files) - 1 - idx) * global_sep)
        
        fig.add_trace(go.Scatter(
            x=x_filtered,
            y=final_y,
            mode='lines',
            name=name,
            line=dict(width=2)
        ))
    
    # Update layout with increased font sizes for titles.
    fig.update_layout(
        xaxis_title="diffraction angle, 2<i>θ</i>",
        xaxis_title_font=dict(family="Dejavu Sans", size=22),
        yaxis_title="intensity, a.u.",
        yaxis_title_font=dict(family="Dejavu Sans", size=22),
        template="simple_white",
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # Determine the x-axis range.
    x_range = angle_max - angle_min
    
    if x_range < 15:
        # For small ranges, keep existing tick settings.
        tick_values = list(range(int(np.ceil(angle_min)), int(np.floor(angle_max)) + 1))
        fig.update_xaxes(
            tickmode="array",
            tickvals=tick_values,
            tickfont=dict(family="Dejavu Sans", size=22),
            ticks="inside",
            ticklen=10,
            showline=True,
            mirror=True,
            automargin=True
        )
    else:
        # For larger ranges, set major ticks (every 10°) to be big and drawn inside.
        major_start = int(np.floor(angle_min / 10.0)) * 10
        fig.update_xaxes(
            tickmode="linear",
            tick0=major_start,
            dtick=10,
            tickfont=dict(family="Dejavu Sans", size=22),
            ticks="inside",
            ticklen=10,
            showline=True,
            mirror=True,
            automargin=True
        )
        
        # Now add custom medium (every 5° excluding 10° multiples) and minor ticks (every 1° excluding 5° multiples)
        shapes = []
        # Medium ticks: every 5° that is not a multiple of 10.
        for tick in np.arange(np.ceil(angle_min/5)*5, angle_max, 5):
            if tick % 10 == 0:
                continue
            shapes.append(dict(
                type="line",
                x0=tick,
                x1=tick,
                xref="x",
                yref="paper",
                # Since ticks point inside from the x-axis (assumed at the bottom, y=0),
                # here y0 is 0 and y1 defines the tick length.
                y0=0,
                y1=0.02,  # medium tick length (adjust as needed)
                line=dict(color="black", width=1.5)
            ))
        # Minor ticks: every 1° that is not a multiple of 5.
        for tick in np.arange(np.ceil(angle_min), angle_max+1, 1):
            if tick % 5 == 0:
                continue
            shapes.append(dict(
                type="line",
                x0=tick,
                x1=tick,
                xref="x",
                yref="paper",
                y0=0,
                y1=0.01,  # minor tick length (adjust as needed)
                line=dict(color="black", width=1)
            ))
        fig.update_layout(shapes=shapes)
    
    # Configure y-axis with a complete box and proper tick fonts.
    fig.update_yaxes(
        tickfont=dict(family="Dejavu Sans", size=22),
        showline=True,
        mirror=True,
        automargin=True
    )
    
    # Force x-axis to display the full angle range.
    fig.update_xaxes(range=[angle_min, angle_max])
    
    return fig

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return decoded.decode('utf-8')