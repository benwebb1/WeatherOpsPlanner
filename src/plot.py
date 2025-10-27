import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio


def plot(df):

    df = df.sort_values(by='Start (hours)', ascending=True)

    # Assign a color to each group
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

    df['Color'] = df['Group'].map(group_colors)

    # Create the figure
    fig = go.Figure()

    # Add each task as a separate bar with color by group and showlegend=False
    for _, row in df.iterrows():
        fig.add_trace(go.Bar(
            x=[row['Duration (hours)']],
            y=[row['ID']],
            base=row['Start (hours)'],
            orientation='h',
            marker_color=row['Color'],
            name=row['Group'],
            showlegend=False,
            customdata=[[row['ID'], row['Duration (hours)'], row['Description'], row['Predecessor IDs'], row['Group'], row['Start (hours)']]],
            hovertemplate=(
                "ID: %{customdata[0]}<br>"
                "Description: %{customdata[2]}<br>"
                "Predecessor(s): %{customdata[3]}<br>"
                "Group: %{customdata[4]}<br>"
                "Duration: %{customdata[1]:.2f} hours<br>"
                "Start: %{customdata[5]:.2f}<br>"
                "End: %{x}<extra></extra>"
            )
        ))

    # Add dummy traces for legend
    for group, color in group_colors.items():
        fig.add_trace(go.Bar(
            x=[None],
            y=[None],
            marker_color=color,
            name=group,
            showlegend=True
        ))

    # Add annotations (ID at the end of each bar)
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row['Start (hours)'] + row['Duration (hours)'],
            y=row['ID'],
            text=str(row['ID']),
            showarrow=False,
            font=dict(color='black', size=12),
            xanchor='left',
            yanchor='middle',
            align='left'
        )

    #vertical red line on x=0hours
    fig.add_vline(
        x=0,
        line_width=2,
        line_dash="dash",
        line_color="red"
    )


    # Update layout
    fig.update_layout(
        barmode='stack',
        xaxis_title='Hour',
        
        xaxis=dict(
                title='Hour',
                dtick=6,              # Set tick (and grid) interval to 6
                showgrid=True,        # Ensure grid lines are visible
                gridcolor='lightgray',# Optional: grid line color
                gridwidth=1           # Optional: grid line thickness
            ),

        yaxis_title='Task ID',
        title='Pipe Pull Operation Schedule',
        xaxis_type='linear',
        yaxis=dict(autorange='reversed')
    )
    pio.renderers.default = 'browser'

    # Save the figure
    fig.show()
    return fig
  
