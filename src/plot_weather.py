import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import ast

def plot_weather(
    schedule_df,
    daylight_windows,
    tide_df,
    tide_windows_df,
    show_weather_restrictions=True  # New argument to toggle weather subplot
):
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

    # Subplot configuration
    if show_weather_restrictions:
        rows = 3
        row_heights = [0.15, 1, 0.2]
        subplot_titles = ("Tide Harwich", "Pipe Pull Operation Schedule", "Weather Restrictions")
        specs = [[{}], [{}], [{"secondary_y": True}]]
    else:
        rows = 2
        row_heights = [0.15, 1]
        subplot_titles = ("Tide Height", "Pipe Pull Operation Schedule")
        specs = [[{}], [{}]]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.05,
        subplot_titles=subplot_titles,
        specs=specs
    )

    # --- Tide Height subplot (row 1) ---
    fig.add_trace(
        go.Scatter(
            x=tide_df['DateTime'],
            y=tide_df['Height'],
            mode='lines',
            line=dict(color='blue', width=2),
            name='Tide Height',
            hovertemplate="Time: %{x}<br>Tide Height: %{y:.2f} m"
        ),
        row=1, col=1
    )
    for _, row in tide_windows_df.iterrows():
        fillcolor = "lightgreen" if row['Type'] == 'HW' else "lightblue" if row['Type'] == 'LW' else "gray"
        fig.add_vrect(
            x0=row['Slack Start'], x1=row['Slack End'],
            fillcolor=fillcolor, opacity=0.3, layer="below", line_width=0,
            annotation_text=row['Type'], annotation_position="top left",
            row=1, col=1
        )

    # --- Schedule subplot (row 2) ---
    for _, row in schedule_df.iterrows():
        bar_color = row['Color']
        try:
            constraints = ast.literal_eval(row['Constraints']) if isinstance(row['Constraints'], str) else row['Constraints']
        except Exception:
            constraints = {}
        tide_req = constraints.get('tide_window_required', False)
        daylight_req = constraints.get('daylight_required', False)
        is_constrained = bool(tide_req or daylight_req)

        fig.add_trace(
            go.Scatter(
                x=[row['Start'], row['End']],
                y=[row['ID'], row['ID']],
                mode='lines',
                line=dict(color=bar_color, width=10),
                name=row['Group'],
                showlegend=False,
                customdata=[[row['ID'], row['Duration'], row['Description'], row['Predecessor IDs'], row['Group'], row['Start'], row['End'], tide_req]] * 2,
                hovertemplate=(
                    "ID: %{customdata[0]}<br>"
                    "Description: %{customdata[2]}<br>"
                    "Predecessor(s): %{customdata[3]}<br>"
                    "Group: %{customdata[4]}<br>"
                    "Duration: %{customdata[1]:.2f} hours<br>"
                    "Start: %{customdata[5]}<br>"
                    "End: %{customdata[6]}<br>"
                    "Tidal Window Constraint: %{customdata[7]}"
                )
            ),
            row=2, col=1
        )

        # Float markers and lines
        if (
            pd.notna(row.get('Float (hours)')) and row['Float (hours)'] > 0 and
            pd.notna(row.get('Earliest Start')) and pd.notna(row.get('Start')) and
            row['Earliest Start'] != row['Start']
        ):
            float_colour = 'grey' if is_constrained else 'black'
            fig.add_trace(
                go.Scatter(
                    x=[row['Earliest Start']],
                    y=[row['ID']],
                    mode='markers',
                    marker=dict(symbol='circle', size=4, color=float_colour),
                    showlegend=False,
                    hoverinfo='skip'
                ),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=[row['Earliest Start'], row['Start']],
                    y=[row['ID'], row['ID']],
                    mode='lines',
                    line=dict(color=float_colour, width=2, dash='dot'),
                    showlegend=False,
                    hoverinfo='skip'
                ),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=[row['Start']],
                    y=[row['ID']],
                    mode='markers',
                    marker=dict(symbol='arrow-right', size=8, color=float_colour),
                    showlegend=False,
                    hoverinfo='skip'
                ),
                row=2, col=1
            )

    # Group legend
    for group, color in group_colors.items():
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None],
                mode='lines',
                line=dict(color=color, width=10),
                name=group,
                showlegend=True
            ),
            row=2, col=1
        )

    # Daylight windows
    for start, end in daylight_windows:
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor="yellow", opacity=0.3, layer="below", line_width=0,
            annotation_text="Daylight", annotation_position="top left",
            row=2, col=1
        )

    # Task name annotations
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
            x=row['End'], y=row['ID'],
            text=str(row['Name']),
            showarrow=False, font=font,
            xanchor='left', yanchor='middle', align='left',
            row=2, col=1
        )

    # Constraint legend
    constraint_legend = {
        "Tide Window Required": "blue",
        "Daylight Required": "orange",
        "Both Required": "red",
        "Float (Unconstrained)": "black",
        "Float (Constrained)": "grey"
    }
    for label, color in constraint_legend.items():
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None],
                mode='markers',
                marker=dict(color=color, size=10),
                name=label,
                showlegend=True
            ),
            row=2, col=1
        )

    # --- Weather Restrictions subplot (row 3, optional) ---
    if show_weather_restrictions:
        restriction_types = [
            'Maximum Wind Speed at 10m (m/s)',
            'Maximum Significant Wave Height, Hs (m)',
            'Maximum Tidal Current (knots)',
            'Maximum Wave Period (s)'
        ]
        restriction_colors = {
            'Maximum Wind Speed at 10m (m/s)': 'red',
            'Maximum Significant Wave Height, Hs (m)': 'blue',
            'Maximum Tidal Current (knots)': 'green',
            'Maximum Wave Period (s)': 'purple'
        }
        primary_y = ['Maximum Significant Wave Height, Hs (m)', 'Maximum Tidal Current (knots)']
        secondary_y = ['Maximum Wind Speed at 10m (m/s)', 'Maximum Wave Period (s)']
        legend_added = set()
        for restriction in restriction_types:
            for _, row in schedule_df.iterrows():
                try:
                    restrictions = ast.literal_eval(row['Weather Restrictions']) if isinstance(row['Weather Restrictions'], str) else row['Weather Restrictions']
                except Exception:
                    restrictions = {}
                if restriction in restrictions:
                    fig.add_trace(
                        go.Scatter(
                            x=[row['Start'], row['End']],
                            y=[restrictions[restriction]] * 2,
                            mode='lines',
                            line=dict(color=restriction_colors[restriction], width=2),
                            name=restriction,
                            showlegend=(restriction not in legend_added),
                            hovertemplate=f"{row['Name']}<br>{restriction}: {restrictions[restriction]}<br>Start: {row['Start']}<br>End: {row['End']}"
                        ),
                        row=3, col=1,
                        secondary_y=(restriction in secondary_y)
                    )
                    legend_added.add(restriction)
        fig.update_yaxes(title_text="Wave Height / Tidal Current", range=[0, 2.4], row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Wind Speed / Wave Period", range=[6, 22], row=3, col=1, secondary_y=True)

    # --- X-axis configuration (always show bottom axis) ---
    x_start = min(schedule_df['Start'])
    x_end = max(schedule_df['End'])
    fig.update_xaxes(range=[x_start, x_end + (x_end - x_start) * 0.05])

    # Ensure x-axis tick labels are visible on all subplot rows
    fig.update_xaxes(showticklabels=True, row=1, col=1)
    fig.update_xaxes(showticklabels=True, row=2, col=1)
    fig.update_xaxes(showticklabels=True, row=3, col=1)

    # Always show bottom x-axis (repeat)
    if show_weather_restrictions:
        fig.update_xaxes(title_text='Datetime', row=3, col=1)
    else:
        fig.update_xaxes(title_text='Datetime', row=2, col=1)

    # Layout
    fig.update_layout(
        height=1400 if show_weather_restrictions else 1100,
        title='Pipe Pull Operation Schedule with Tide and Weather Restrictions' if show_weather_restrictions else 'Pipe Pull Operation Schedule with Tide',
        yaxis_title='Tide Height (m)',
        yaxis2_title='Task ID',
        yaxis2=dict(autorange='reversed'),
        legend_title='Group & Constraints',
        legend=dict(font=dict(size=12))
    )
    pio.renderers.default = 'browser'
    fig.show()
    return fig