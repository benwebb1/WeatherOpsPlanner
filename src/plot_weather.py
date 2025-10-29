import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import ast

def plot_weather(schedule_df, daylight_windows, tide_df, tide_windows_df):
    group_colors = {
        "Excavator": "#800080",
        "Deck hands": "#808080",
        "Jack-up barge": "#FF0000",
        "Horizontal Directional Drilling": "#FFAE00",
        "Pipe Management": "#90EE90",
        "Crew Transfer Vessel": "#FFA4B4",
        "Winch": "#FCFC5F",
        "Diving": "#018D8D",
        "Crane": "#BA71FF",
    }

    schedule_df['Color'] = schedule_df['Group'].map(group_colors)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.15, 0.8],
        vertical_spacing=0.05,
        subplot_titles=("Tide Height", "Pipe Pull Operation Schedule")
    )

    fig.add_trace(go.Scatter(
        x=tide_df['DateTime'],
        y=tide_df['Height'],
        mode='lines',
        line=dict(color='blue', width=2),
        name='Tide Height',
        hovertemplate="Time: %{x}<br>Tide Height: %{y:.2f} m<extra></extra>"
    ), row=1, col=1)

    for _, row in tide_windows_df.iterrows():
        fillcolor = "lightgreen" if row['Type'] == 'HW' else "lightblue" if row['Type'] == 'LW' else "gray"
        fig.add_vrect(
            x0=row['Slack Start'], x1=row['Slack End'],
            fillcolor=fillcolor, opacity=0.3,
            layer="below", line_width=0,
            annotation_text=row['Type'], annotation_position="top left",
            row=1, col=1
        )

    for _, row in schedule_df.iterrows():
        bar_color = row['Color']
        try:
            constraints = ast.literal_eval(row['Constraints']) if isinstance(row['Constraints'], str) else row['Constraints']
        except Exception:
            constraints = {}

        tide_req = constraints.get('tide_window_required', False)
        daylight_req = constraints.get('daylight_required', False)

        fig.add_trace(go.Scatter(
            x=[row['Start'], row['End']],
            y=[row['ID'], row['ID']],
            mode='lines',
            line=dict(color=bar_color, width=10),
            name=row['Group'],
            showlegend=False,
            customdata=[[row['ID'], row['Duration'], row['Description'], row['Predecessor IDs'], row['Group'], row['Start'], row['End'], tide_req]] * 2,
            hovertemplate=(
                "ID: %{customdata[0]}<br>" +
                "Description: %{customdata[2]}<br>" +
                "Predecessor(s): %{customdata[3]}<br>" +
                "Group: %{customdata[4]}<br>" +
                "Duration: %{customdata[1]:.2f} hours<br>" +
                "Start: %{customdata[5]}<br>" +
                "End: %{customdata[6]}<br>" +
                "Tidal Window Constraint: %{customdata[7]}<extra></extra>"
            )
        ), row=2, col=1)

    for group, color in group_colors.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            line=dict(color=color, width=10),
            name=group,
            showlegend=True
        ), row=2, col=1)

    for start, end in daylight_windows:
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor="yellow", opacity=0.3,
            layer="below", line_width=0,
            annotation_text="Daylight", annotation_position="top left",
            row=2, col=1
        )

    # Add annotations with color logic
    for _, row in schedule_df.iterrows():
        try:
            constraints = ast.literal_eval(row['Constraints']) if isinstance(row['Constraints'], str) else row['Constraints']
        except Exception:
            constraints = {}

        tide_req = constraints.get('tide_window_required', False)
        daylight_req = constraints.get('daylight_required', False)

        if tide_req and daylight_req:
            font = dict(color='red', size=14, family='Arial Black')
        elif tide_req:
            font = dict(color='blue', size=14, family='Arial Black')
        elif daylight_req:
            font = dict(color='orange', size=14, family='Arial Black')
        else:
            font = dict(color='black', size=14)

        fig.add_annotation(
            x=row['End'],
            y=row['ID'],
            text=str(row['Name']),
            showarrow=False,
            font=font,
            xanchor='left',
            yanchor='middle',
            align='left',
            row=2, col=1
        )

    # Add custom legend for constraint colors
    constraint_legend = {
        "Tide Window Required": "blue",
        "Daylight Required": "orange",
        "Both Required": "red"
    }

    for label, color in constraint_legend.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='text',
            text=[label],
            textfont=dict(color=color, size=14, family='Arial Black'),
            name=label,
            showlegend=True
        ), row=2, col=1)

    x_start = min(schedule_df['Start'])
    x_end = max(schedule_df['End'])
    fig.update_xaxes(range=[x_start, x_end + (x_end - x_start) * 0.05])

    fig.update_layout(
        height=1200,
        title='Pipe Pull Operation Schedule with Tide Data',
        xaxis_title='Datetime',
        yaxis_title='Tide Height (m)',
        yaxis2_title='Task ID',
        yaxis2=dict(autorange='reversed'),
        legend_title='Group & Constraints'
    )

    pio.renderers.default = 'browser'
    fig.show()
    return fig