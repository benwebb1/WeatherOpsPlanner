import pandas as pd

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

        self.is_critical = False


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


def is_weather_ok(activity, time_index, weather_data):
    data = weather_data.get(time_index, {})
    current_ok = activity.max_tidal_current is None or data.get("tidal_current", 0) <= activity.max_tidal_current
    level_ok = activity.min_tidal_level is None or data.get("tidal_level", 0) >= activity.min_tidal_level
    return current_ok and level_ok


def schedule_activities(activities, weather_data=None, analysis_interval=1.0):
    """
    analysis_interval: time step in hours (e.g., 1.0 = hourly, 0.5 = half-hourly, 0.1667 = 10 min)
    """
    activity_map = {act.id: act for act in activities}

    def compute_times(activity):
        if activity.start is not None:
            return
        if not activity.predecessors:
            start_time = 0.0
        else:
            max_end = 0.0
            for pred_id in activity.predecessors:
                pred = activity_map.get(pred_id)
                if pred:
                    compute_times(pred)
                    max_end = max(max_end, pred.end)
            start_time = max_end

        # Delay until weather is OK
        if weather_data:
            while not is_weather_ok(activity, round(start_time / analysis_interval), weather_data):
                start_time += analysis_interval

        activity.start = start_time
        activity.end = activity.start + activity.duration

    for activity in activities:
        compute_times(activity)

    # Backward pass
    project_end = max(act.end for act in activities)
    for act in activities:
        act.latest_end = project_end
        act.latest_start = act.latest_end - act.duration

    for act in reversed(activities):
        for pred_id in act.predecessors:
            pred = activity_map.get(pred_id)
            if pred:
                pred.latest_end = min(pred.latest_end, act.latest_start)
                pred.latest_start = pred.latest_end - pred.duration

    # Slack and critical path
    for act in activities:
        act.slack = act.latest_start - act.start
        act.is_critical = act.slack == 0

    return activities


def scheduled_df(scheduled_activities):
    return pd.DataFrame([{
        "ID": act.id,
        "Description": act.description,
        "Duration (hours)": act.duration,
        "Start (hours)": act.start,
        "End (hours)": act.end,
        "Group": act.group,
        "Predecessor IDs": act.predecessors,
        "Max Tidal Current (m/s)": act.max_tidal_current,
        "Min Tidal Level (mCD)": act.min_tidal_level,
        "Critical": act.is_critical
    } for act in scheduled_activities])


def shift_start_end(schedule_df, zero_hour_activity="Punch out of pilot"):
    zero_hour = schedule_df.loc[schedule_df['Description'] == zero_hour_activity, 'Start (hours)'].values[0]
    schedule_df['Start (hours)'] -= zero_hour
    schedule_df['End (hours)'] -= zero_hour
    return schedule_df