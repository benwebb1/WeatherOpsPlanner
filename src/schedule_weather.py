import pandas as pd
from datetime import datetime, timedelta

class Activity:
    """
    Represents a single scheduled activity with dependencies and constraints.

    Attributes:
        id (str): Unique identifier for the activity.
        description (str): Human-readable description.
        predecessors (list): List of IDs of activities that must finish before this one starts.
        successors (list): List of IDs for activities that follow this one (optional).
        duration (float): Duration in hours.
        group (str): Logical group or category this activity belongs to.
        constraints (dict): Dictionary of environmental/weather constraints,
                            including daylight_required and tide_window_required (booleans).
        start (datetime): Scheduled start time (to be computed).
        end (datetime): Scheduled end time (to be computed).
        latest_start (datetime): Latest allowable start time (for critical path).
        latest_end (datetime): Latest allowable end time (for critical path).
        slack (float): Slack time in hours.
        is_critical (bool): True if activity lies on critical path.
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

class Scheduler:
    """
    Manages the scheduling of activities considering dependencies and environmental constraints.

    Args:
        activities (list of Activity): List of activities to schedule.
        weather_data (pandas.DataFrame): Weather and environmental data indexed by datetime.
        start_datetime (datetime): Schedule start reference time.

        daylight_windows (list of (datetime, datetime)): Allowed time ranges for daylight constraints.
        tide_windows (list of (datetime, datetime)): Allowed time ranges for tide constraints.

    Methods:
        schedule(): Executes scheduling, applying constraints and computing critical path.
        to_dataframe(): Exports scheduled activities as a pandas DataFrame.
    """
    def __init__(self, activities, weather_data=None, daylight_windows=None,
                 tide_windows=None, start_datetime=None):
        self.activities = activities
        self.weather_data = weather_data
        self.daylight_windows = daylight_windows or []
        self.tide_windows = tide_windows or []
        self.start_datetime = start_datetime or datetime.now()
        self.activity_map = {act.id: act for act in activities}

    def check_time_window(self, windows, start_time, duration):
        """
        Check if the full activity duration fits entirely within any of the given time windows.
        
        Args:
            windows (list of (datetime, datetime)): List of allowed time windows.
            start_time (datetime): Proposed start time.
            duration (float): Duration in hours.

        Returns:
            bool: True if activity fits completely inside at least one window.
        """
        end_time = start_time + timedelta(hours=duration)
        return any(start_time >= w[0] and end_time <= w[1] for w in windows)

    def check_constraints(self, activity, start_time):
        """
        Checks if the activity can be scheduled starting at start_time without violating constraints.

        Supports weather constraints dynamically, plus daylight and tide windows conditionally.

        Args:
            activity (Activity): The activity to check.
            start_time (datetime): Proposed start time.

        Returns:
            bool: True if constraints are met; False otherwise.
        """
        end_time = start_time + timedelta(hours=activity.duration)

        # Weather constraints check if weather data available
        if self.weather_data is not None:
            window = self.weather_data[
                (self.weather_data['datetime'] >= start_time) &
                (self.weather_data['datetime'] < end_time)
            ]
            required_len = int(activity.duration * 60)  # assume 1-minute weather data frequency
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

        # Daylight window constraint if requested
        if activity.constraints.get('daylight_required', False):
            if not self.check_time_window(self.daylight_windows, start_time, activity.duration):
                return False

        # Tide window constraint if requested
        if activity.constraints.get('tide_window_required', False):
            if not self.check_time_window(self.tide_windows, start_time, activity.duration):
                return False

        return True

    def find_next_valid_start(self, activity, candidate_start):
        """
        Finds earliest start time >= candidate_start satisfying constraints.

        Jumps to next window starts of daylight or tide or increments by 1 minute fallback.

        Args:
            activity (Activity): Activity to schedule.
            candidate_start (datetime): Initial proposed start.

        Returns:
            datetime: Valid start time meeting constraints.
        """
        while not self.check_constraints(activity, candidate_start):
            next_times = []

            if activity.constraints.get('tide_window_required', False):
                next_tides = [tw[0] for tw in self.tide_windows if tw[0] > candidate_start]
                if next_tides:
                    next_times.append(min(next_tides))

            if activity.constraints.get('daylight_required', False):
                next_daylights = [dw[0] for dw in self.daylight_windows if dw[0] > candidate_start]
                if next_daylights:
                    next_times.append(min(next_daylights))

            if next_times:
                candidate_start = min(next_times)
            else:
                candidate_start += timedelta(minutes=1)

        return candidate_start

    def compute_start_end(self, activity):
        """
        Recursively compute start and end time for an activity considering dependencies.

        Args:
            activity (Activity): Activity to schedule.
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

        Returns:
            list: Scheduled Activity objects.
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
            "Critical": act.is_critical
        } for act in self.activities])

def generate_activity_list(act_df):
    """
    Generate Activity objects from DataFrame, including boolean daylight and tide window flags.

    Args:
        act_df (pd.DataFrame): DataFrame with activity and constraints data.

    Returns:
        list: List of Activity objects.
    """
    act_list = []
    for _, row in act_df.iterrows():
        preds = [] if pd.isna(row.get("Predecessor ID(s)", None)) or row.get("Predecessor ID(s)", None) == "-" else str(row["Predecessor ID(s)"]).split(",")
        succs = [] if pd.isna(row.get("Successor ID(s)", "-")) or row.get("Successor ID(s)", "-") == "-" else str(row["Successor ID(s)"]).split(",")
        
        # Extract constraints with boolean daylight and tide window flags
        constraints = {}
        if "Daylight Required" in row:
            constraints["daylight_required"] = bool(row["Daylight Required"])
        if "Tide Window Required" in row:
            constraints["tide_window_required"] = bool(row["Tide Window Required"])
        # Add other constraints if present (e.g., max_wind_speed, max_wave_height, etc.)
        for key in row.index:
            if key.lower() in ['max tidal current (m/s)', 'min tidal level (mcd)', 'max wind speed (m/s)', 'max wave height (m)']:
                # Normalize key to snake_case format keys
                norm_key = key.lower().replace(' ', '_').replace('(', '').replace(')', '')
                if pd.notna(row[key]):
                    constraints[norm_key] = row[key]

        act_list.append(Activity(
            row["ID"],
            row["Sub Activity"],
            preds,
            succs,
            row["Duration (hours)"],
            row["Group"],
            constraints
        ))
    return act_list

