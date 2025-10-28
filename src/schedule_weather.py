import pandas as pd
from datetime import datetime, timedelta

class Activity:
    """
    Represents a single scheduled activity with dependencies and constraints.
    """
    def __init__(self, id, description, predecessors, successors, duration, group,
                 constraints=None):
        self.id = id
        self.description = description
        self.predecessors = predecessors
        self.successors = successors
        self.duration = duration  # in hours
        self.group = group
        self.constraints = constraints or {}
        self.start = None
        self.end = None
        self.latest_start = None
        self.latest_end = None
        self.slack = None
        self.is_critical = False
        self.tide_window_mismatch = False  # Flag if duration exceeds tide window

def load_daylight_windows(csv_path):
    """
    Load daylight windows from CSV.
    """
    df = pd.read_csv(csv_path)
    windows = []
    for _, row in df.iterrows():
        date = row['Date']
        sunrise = datetime.strptime(f"{date} {row['Sunrise']}", "%Y-%m-%d %H:%M:%S")
        sunset = datetime.strptime(f"{date} {row['Sunset']}", "%Y-%m-%d %H:%M:%S")
        windows.append((sunrise, sunset))
    return windows

def load_tide_windows(csv_path):
    """
    Load tide windows from CSV.
    """
    df = pd.read_csv(csv_path)
    hw_windows = []
    lw_windows = []
    for _, row in df.iterrows():
        slack_start = datetime.strptime(row['Slack Start'], "%Y-%m-%d %H:%M:%S")
        slack_end = datetime.strptime(row['Slack End'], "%Y-%m-%d %H:%M:%S")
        if row['Type'] == 'HW':
            hw_windows.append((slack_start, slack_end))
        elif row['Type'] == 'LW':
            lw_windows.append((slack_start, slack_end))
    return hw_windows, lw_windows

class Scheduler:
    """
    Manages the scheduling of activities considering dependencies and environmental constraints.
    """
    def __init__(self, activities, weather_data=None, daylight_csv=None,
                 tide_csv=None, start_datetime=None):
        self.activities = activities
        self.weather_data = weather_data
        self.daylight_windows = load_daylight_windows(daylight_csv) if daylight_csv else []
        hw_windows, lw_windows = load_tide_windows(tide_csv) if tide_csv else ([], [])
        self.tide_windows = {'HW': hw_windows, 'LW': lw_windows}
        self.start_datetime = start_datetime or datetime.now()
        self.activity_map = {act.id: act for act in activities}

    def check_time_window(self, windows, start_time, duration):
        """
        Check if the full activity duration fits entirely within any of the given time windows.
        """
        end_time = start_time + timedelta(hours=duration)
        return any(start_time >= w[0] and end_time <= w[1] for w in windows)

    def check_constraints(self, activity, start_time):
        """
        Checks if the activity can be scheduled starting at start_time without violating constraints.
        """
        end_time = start_time + timedelta(hours=activity.duration)

        # Weather constraints - not yet used as no weather data is provided
        if self.weather_data is not None:
            window = self.weather_data[
                (self.weather_data['datetime'] >= start_time) &
                (self.weather_data['datetime'] < end_time)
            ]
            required_len = int(activity.duration * 60)
            if len(window) < required_len:
                return False

            for key, limit in activity.constraints.items():
                if key.startswith('max_'):
                    col = key[4:]
                    if col in window.columns and any(window[col] > limit):
                        return False
                elif key.startswith('min_'):
                    col = key[4:]
                    if col in window.columns and any(window[col] < limit):
                        return False
                else:
                    col = key
                    if col in window.columns and any(window[col] != limit):
                        return False

        # Daylight constraint
        if activity.constraints.get('daylight_required', False):
            if not self.check_time_window(self.daylight_windows, start_time, activity.duration):
                return False

        # Tide constraint
        tide_req = activity.constraints.get('tide_window_required', False)
        if tide_req:
            if tide_req == 'slackhw':
                if not self.check_time_window(self.tide_windows['HW'], start_time, activity.duration):
                    return False
            elif tide_req == 'slack':
                combined_windows = self.tide_windows['HW'] + self.tide_windows['LW']
                if not self.check_time_window(combined_windows, start_time, activity.duration):
                    return False

        return True

    
    def find_next_valid_start(self, activity, candidate_start):
        """
        Finds earliest start time >= candidate_start satisfying constraints.
        If both daylight and tide constraints are required, the activity is only scheduled when:
        - Its center aligns with the center of a tide window
        - The entire activity fits within a daylight window
        """
        tide_req = activity.constraints.get('tide_window_required', False)
        daylight_req = activity.constraints.get('daylight_required', False)

        while not self.check_constraints(activity, candidate_start):
            if tide_req:
                windows = []
                if tide_req.lower() == 'slackhw':
                    windows = self.tide_windows['HW']
                elif tide_req.lower() == 'slack':
                    windows = self.tide_windows['HW'] + self.tide_windows['LW']

                for window_start, window_end in windows:
                    if window_start >= candidate_start:
                        center = window_start + (window_end - window_start) / 2
                        proposed_start = center - timedelta(hours=activity.duration / 2)
                        proposed_end = proposed_start + timedelta(hours=activity.duration)

                        # Check if proposed time fits within a daylight window
                        if daylight_req:
                            for dl_start, dl_end in self.daylight_windows:
                                if dl_start <= proposed_start and dl_end >= proposed_end:
                                    activity.tide_window_mismatch = False
                                    return proposed_start
                        else:
                            activity.tide_window_mismatch = False
                            return proposed_start

            # If only daylight is required and no tide constraint matched
            if daylight_req:
                for dl_start, dl_end in self.daylight_windows:
                    if dl_start >= candidate_start:
                        if (dl_end - dl_start).total_seconds() / 3600 >= activity.duration:
                            return dl_start

            # If no valid time found, increment candidate_start
            candidate_start += timedelta(minutes=1)

        return candidate_start


    def compute_start_end(self, activity):
        """
        Recursively compute start and end time for an activity considering dependencies.
        """
        if activity.start is not None:
            return

        for pred_id in activity.predecessors:
            pred = self.activity_map.get(pred_id)
            if pred:
                self.compute_start_end(pred)

        if not activity.predecessors:
            candidate_start = self.start_datetime
        else:
            candidate_start = max(self.activity_map[pred].end for pred in activity.predecessors if self.activity_map.get(pred))

        activity.start = self.find_next_valid_start(activity, candidate_start)
        activity.end = activity.start + timedelta(hours=activity.duration)

    def schedule(self, run_critical_path=True):
        """
        Schedule all activities respecting dependencies and constraints.
        """
        for activity in self.activities:
            self.compute_start_end(activity)

        if run_critical_path:
            self.estimate_critical_path()

        return self.activities

    def estimate_critical_path(self):
        """
        Compute latest start/end, slack and critical activity flags with backward pass.
        """
        project_end = max(act.end for act in self.activities)

        for act in self.activities:
            act.latest_end = project_end
            act.latest_start = act.latest_end - timedelta(hours=act.duration)

        for act in reversed(self.activities):
            for pred_id in act.predecessors:
                pred = self.activity_map.get(pred_id)
                if pred and pred.latest_end > act.latest_start:
                    pred.latest_end = act.latest_start
                    pred.latest_start = pred.latest_end - timedelta(hours=pred.duration)

        for act in self.activities:
            act.slack = (act.latest_start - act.start).total_seconds() / 3600
            act.is_critical = (act.slack == 0)

    def to_dataframe(self):
        """
        Export scheduled activities as pandas DataFrame.
        """
        return pd.DataFrame([{
            "ID": act.id,
            "Description": act.description,
            "Duration (hours)": act.duration,
            "Start": act.start,
            "End": act.end,
            "Group": act.group,
            "Predecessor IDs": act.predecessors,
            "Constraints": act.constraints,
            "Critical": act.is_critical,
            "Tide Window Mismatch": act.tide_window_mismatch
        } for act in self.activities])

def generate_activity_list(act_df, constraints_df):
    """
    Generate Activity objects from DataFrame, including environmental/weather constraints.
    """
    constraint_map = {}
    for _, row in constraints_df.iterrows():
        cid = row.get("Constraint_ID")
        if pd.isna(cid):
            continue
        cdict = {}
        daylight_col = [col for col in row.index if "Daylight" in col][0]
        cdict["daylight_required"] = bool(row[daylight_col]) if not pd.isna(row[daylight_col]) and str(row[daylight_col]).strip().lower() in ["yes", "y", "true", "1"] else False
        tide_col = [col for col in row.index if "Tidal Window" in col][0]
        tide_val = str(row[tide_col]).strip().lower() if not pd.isna(row[tide_col]) else ""
        cdict["tide_window_required"] = tide_val if tide_val in ["slack", "slackhw"] else False
        if not pd.isna(row.get("Maximum Wind Speed at 10m (m/s)", None)):
            cdict["max_wind_speed"] = row["Maximum Wind Speed at 10m (m/s)"]
        if not pd.isna(row.get("Maximum Significant Wave Height, Hs (m)", None)):
            cdict["max_wave_height"] = row["Maximum Significant Wave Height, Hs (m)"]
        if not pd.isna(row.get("Maximum Tidal Current (knots)", None)):
            cdict["max_tidal_current"] = row["Maximum Tidal Current (knots)"]
        if not pd.isna(row.get("Minimum Tidal Level (mOD)", None)):
            cdict["min_tidal_level"] = row["Minimum Tidal Level (mOD)"]
        if not pd.isna(row.get("Visibility (nm)", None)):
            cdict["min_visibility"] = row["Visibility (nm)"]
        constraint_map[cid] = cdict

    act_list = []
    for _, row in act_df.iterrows():
        preds = [] if pd.isna(row.get("Predecessor ID(s)", None)) or row.get("Predecessor ID(s)", None) == "-" else [x.strip() for x in str(row["Predecessor ID(s)"]).split(",")]
        succs = []
        constraints = {}
        cid = row.get("Constraint_ID", None)
        if pd.notna(cid) and cid in constraint_map:
            constraints.update(constraint_map[cid])

        act_list.append(Activity(
            id=row["ID"],
            description=row["Sub Activity"],
            predecessors=preds,
            successors=succs,
            duration=row["Duration (hours)"],
            group=row["Group"],
            constraints=constraints
        ))
    return act_list
