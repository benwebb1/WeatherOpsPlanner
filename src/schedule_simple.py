import pandas as pd

class Activity:
    def __init__(self, id, description, predecessors, successors, duration, group):
        self.id = id
        self.description = description
        self.predecessors = predecessors
        self.successors = successors
        self.duration = duration
        self.group = group
        self.start = None
        self.end = None

def generate_activity_list(act_df):
    act_list = []
    for _, row in act_df.iterrows():
        # Handle predecessors
        pred_raw = row["Predecessor ID(s)"]
        preds = [] if pd.isna(pred_raw) or pred_raw == "-" else str(pred_raw).split(",")

        # Handle successors
        succ_raw = row["Successor ID(s)"] if "Successor ID(s)" in row else "-"
        succs = [] if pd.isna(succ_raw) or succ_raw == "-" else str(succ_raw).split(",")

        # Create Activity object
        act_list.append(Activity(
            row["ID"],
            row["Sub Activity"],
            preds,
            succs,
            row["Duration (hours)"],
            row["Group"]
        ))
    return act_df


def schedule_activities(activities):
    activity_map = {act.id: act for act in activities}

    # Forward pass: compute earliest start and end
    def compute_times(activity):
        if activity.start is not None:
            return
        if not activity.predecessors:
            activity.start = 0
        else:
            max_end = 0
            for pred_id in activity.predecessors:
                pred = activity_map.get(pred_id)
                if pred:
                    compute_times(pred)
                    max_end = max(max_end, pred.end)
            activity.start = max_end
        activity.end = activity.start + activity.duration

    for activity in activities:
        compute_times(activity)



def sheduled_df(scheduled_activities):
    # Create a DataFrame with computed start and end times
    schedule_df = pd.DataFrame([{
        "ID": act.id,
        "Description": act.description,
        "Duration (hours)": act.duration,
        "Start (hours)": act.start,
        "End (hours)": act.end,
        "Group": act.group,
        "Predecessor IDs": act.predecessors
    } for act in scheduled_activities])
    return schedule_df

def shift_start_end(schedule_df, zero_hour_activity="Punch out of pilot"):
    zero_hour = schedule_df.loc[schedule_df['Description'] == zero_hour_activity, 'Start (hours)'].values[0]
    schedule_df['Start (hours)'] = schedule_df['Start (hours)'] - zero_hour
    schedule_df['End (hours)'] = schedule_df['End (hours)'] - zero_hour
    return schedule_df