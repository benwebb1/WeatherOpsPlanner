import pandas as pd
from datetime import datetime, timedelta

# Activity class definition
class Activity:
    def __init__(self, id, description, predecessors, successors, duration, group,
                 max_tidal_current=None, min_tidal_level=None):
        self.id = id
        self.description = description
        self.predecessors = predecessors
        self.successors = successors
        self.duration = duration  # in hours
        self.group = group
        self.max_tidal_current = max_tidal_current
        self.min_tidal_level = min_tidal_level
        self.start = None
        self.end = None
        self.latest_start = None
        self.latest_end = None
        self.slack = None
        self.is_critical = False

# Generate activity list from DataFrame
def generate_activity_list(act_df):
    act_list = []
    for _, row in act_df.iterrows():
        preds = [] if pd.isna(row["Predecessor ID(s)"]) or row["Predecessor ID(s)"] == "-" else str(row["Predecessor ID(s)"]).split(",")
        succs = [] if pd.isna(row.get("Successor ID(s)", "-")) or row.get("Successor ID(s)", "-") == "-" else str(row["Successor ID(s)"]).split(",")
        act_list.append(Activity(
            row["ID"],
            row["Sub Activity"],
            preds,
            succs,
            row["Duration (hours)"],
            row["Group"],
            row.get("Max Tidal Current (m/s)", None),
            row.get("Min Tidal Level (mCD)", None)
        ))
    return act_list
# Check if weather conditions are acceptable
def is_weather_ok(activity, timestamp, weather_data):
    row = weather_data[weather_data['datetime'] == timestamp]
    if row.empty:
        return False
    data = row.iloc[0]
    current_ok = activity.max_tidal_current is None or data['tidal_current'] <= activity.max_tidal_current
    level_ok = activity.min_tidal_level is None or data['tidal_level'] >= activity.min_tidal_level
    return current_ok and level_ok

# Schedule activities with weather constraints
def schedule_activities(activities, weather_data=None, analysis_interval=1.0, start_datetime=None, run_critical_path=True):
    if start_datetime is None:
        start_datetime = datetime.now()

    activity_map = {act.id: act for act in activities}

    def compute_times(activity):
        if activity.start is not None:
            return
        if not activity.predecessors:
            start_time = start_datetime
        else:
            max_end = start_datetime
            for pred_id in activity.predecessors:
                pred = activity_map.get(pred_id)
                if pred:
                    compute_times(pred)
                    max_end = max(max_end, pred.end)
            start_time = max_end

        # Delay until weather is OK
        if weather_data is not None:
            while not is_weather_ok(activity, start_time, weather_data):
                start_time += timedelta(hours=analysis_interval)

        activity.start = start_time
        activity.end = activity.start + timedelta(hours=activity.duration)

    for activity in activities:
        compute_times(activity)

    if run_critical_path:
        activities = estimate_critical_path(activities)

    return activities

# Optional backward pass and critical path analysis
def estimate_critical_path(activities):
    activity_map = {act.id: act for act in activities}
    project_end = max(act.end for act in activities)

    for act in activities:
        act.latest_end = project_end
        act.latest_start = act.latest_end - timedelta(hours=act.duration)

    for act in reversed(activities):
        for pred_id in act.predecessors:
            pred = activity_map.get(pred_id)
            if pred:
                pred.latest_end = min(pred.latest_end, act.latest_start)
                pred.latest_start = pred.latest_end - timedelta(hours=pred.duration)

    for act in activities:
        act.slack = (act.latest_start - act.start).total_seconds() / 3600
        act.is_critical = act.slack == 0

    return activities

# Convert scheduled activities to DataFrame
def scheduled_df(scheduled_activities):
    return pd.DataFrame([{
        "ID": act.id,
        "Description": act.description,
        "Duration (hours)": act.duration,
        "Start": act.start,
        "End": act.end,
        "Group": act.group,
        "Predecessor IDs": act.predecessors,
        "Max Tidal Current (m/s)": act.max_tidal_current,
        "Min Tidal Level (mCD)": act.min_tidal_level,
        "Critical": act.is_critical
    } for act in scheduled_activities])

# Shift schedule so a reference activity starts at zero
def shift_start_end(schedule_df, zero_hour_activity="Punch out of pilot"):
    zero_time = schedule_df.loc[schedule_df['Description'] == zero_hour_activity, 'Start'].values[0]
    schedule_df['Start'] = pd.to_datetime(schedule_df['Start']) - pd.to_datetime(zero_time)
    schedule_df['End'] = pd.to_datetime(schedule_df['End']) - pd.to_datetime(zero_time)
    return schedule_df