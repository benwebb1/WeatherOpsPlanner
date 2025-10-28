import pandas as pd
from datetime import datetime, timedelta

class Activity:
    """
    Represents a single scheduled activity with dependencies and constraints.
    """
    def __init__(self, id, name, description, predecessors, duration, group, constraints=None):
        self.id = id
        self.name = name
        self.description = description
        self.predecessors = predecessors  # list of ids
        self.duration = duration  # in hours
        self.group = group
        self.constraints = constraints or {}
        self.start = None
        self.end = None
        self.successors = []  # to be populated later

class Scheduler:
    """
    Manages fast, simplified scheduling with constraints aligned efficiently
    around tide and daylight windows, avoiding minute-by-minute scanning.
    """
    def __init__(self, activities, daylight_windows=None, hw_tide_windows=None, lw_tide_windows=None):
        self.activities = activities
        self.daylight_windows = daylight_windows if daylight_windows else []
        self.tide_windows = {'HW': hw_tide_windows or [], 'LW': lw_tide_windows or []}
        self.activity_map = {act.id: act for act in activities}
        # Build successor relations from predecessors
        for act in self.activities:
            act.successors = []
        for act in self.activities:
            for pred_id in act.predecessors:
                if pred_id in self.activity_map:
                    self.activity_map[pred_id].successors.append(act.id)

    def find_aligned_start(self, activity, earliest_start):
        """
        Find a start time aligned to constraints without minute steps,
        prioritizing tide center alignment, then daylight overlap.
        """
        duration_td = timedelta(hours=activity.duration)
        tide_req = activity.constraints.get('tide_window_required', False)
        daylight_req = activity.constraints.get('daylight_required', False)

        # Helper to check if activity overlaps daylight at proposed start
        def overlaps_daylight(start):
            end = start + duration_td
            return any(
                (min(dl_end, end) - max(dl_start, start)).total_seconds() > 0
                for dl_start, dl_end in self.daylight_windows
            )

        # If tide window required, choose window center
        if tide_req:
            windows = []
            if tide_req == 'slackhw':
                windows = self.tide_windows['HW']
            elif tide_req == 'slack':
                windows = self.tide_windows['HW'] + self.tide_windows['LW']
            for w_start, w_end in windows:
                window_center = w_start + (w_end - w_start) / 2
                proposed_start = window_center - duration_td / 2
                if proposed_start >= earliest_start:
                    if not daylight_req or overlaps_daylight(proposed_start):
                        return proposed_start

        # Else, check daylight windows
        if daylight_req:
            for dl_start, dl_end in self.daylight_windows:
                if dl_start >= earliest_start and (dl_end - dl_start) >= duration_td:
                    return dl_start

        # fallback: earliest_start
        return earliest_start

    def compute_start_end_forward(self, activity):
        """
        Compute start/end based on predecessors, then clamp to constraints.
        """
        if activity.start is not None:
            return
        if activity.predecessors:
            for pred_id in activity.predecessors:
                self.compute_start_end_forward(self.activity_map[pred_id])
            earliest_start = max(self.activity_map[pred_id].end for pred_id in activity.predecessors)
        else:
            earliest_start = datetime.min
        activity.start = self.find_aligned_start(activity, earliest_start)
        activity.end = activity.start + timedelta(hours=activity.duration)

    def compute_start_end_reverse(self, activity):
        """
        Compute start/end based on successors, then clamp to constraints.
        """
        if activity.end is not None:
            return
        if activity.successors:
            for succ_id in activity.successors:
                self.compute_start_end_reverse(self.activity_map[succ_id])
            candidate_end = min(self.activity_map[succ_id].start for succ_id in activity.successors)
        else:
            candidate_end = activity.end  # preset for target

        # Align end to tide center or daylight
        def align_end():
            duration_td = timedelta(hours=activity.duration)
            # For tide alignment - pick nearest center
            if activity.constraints.get('tide_window_required', False):
                if activity.constraints['tide_window_required'] == 'slackhw':
                    windows = self.tide_windows['HW']
                elif activity.constraints['tide_window_required'] == 'slack':
                    windows = self.tide_windows['HW'] + self.tide_windows['LW']
                centers = [w_start + (w_end - w_start) / 2 for w_start, w_end in windows]
                if centers:
                    closest_center = min(centers, key=lambda c: abs(c - (candidate_end - duration_td/2)))
                    aligned_end = closest_center + duration_td/2
                else:
                    aligned_end = candidate_end
            else:
                aligned_end = candidate_end

            # Optional daylight overlap check if needed
            if activity.constraints.get('daylight_required', False):
                aligned_end = max(aligned_end,  min(dl_end for dl_start, dl_end in self.daylight_windows))
                # Or more sophisticated if necessary

            return aligned_end

        activity.end = align_end()
        activity.start = activity.end - timedelta(hours=activity.duration)

    def schedule_around_target(self, target_name, target_end_time):
        """
        Setup full schedule: back from target, then forward from target.
        """
        for act in self.activities:
            act.start = None
            act.end = None

        target_act = next((a for a in self.activities if a.name == target_name), None)
        if not target_act:
            raise ValueError(f"Target activity '{target_name}' not found.")

        # Set target end
        target_act.end = target_end_time
        target_act.start = target_end_time - timedelta(hours=target_act.duration)

        # Backward schedule predecesors
        self.compute_start_end_reverse(target_act)

        # Forward schedule successors
        def recurse(act):
            for succ_id in act.successors:
                succ = self.activity_map[succ_id]
                if succ.start and succ.end:
                    continue
                # schedule predecessors
                for pred_id in succ.predecessors:
                    self.compute_start_end_forward(self.activity_map[pred_id])
                # schedule this successor
                self.compute_start_end_forward(succ)
                recurse(succ)
        recurse(target_act)
        return self.activities

    def to_dataframe(self):
        return pd.DataFrame([{
            "ID": a.id,
            "Name": a.name,
            "Start": a.start,
            "End": a.end,
            "Duration": a.duration,
            "Group": a.group,
            "Description": a.description,
            "Predecessor IDs": ", ".join(a.predecessors)

        } for a in self.activities])

def generate_activity_list(act_df, constraints_df):
    """
    Convert DataFrame to activities list with constraints.
    """
    constraints_map = {}
    for _, row in constraints_df.iterrows():
        cid = row.get("Constraint_ID")
        if pd.isna(cid):
            continue
        cdict = {}
        for col in row.index:
            val = row[col]
            if "Daylight" in col:
                cdict["daylight_required"] = bool(str(val).strip().lower() in ["yes","y","true","1"])
            elif "Tidal Window" in col:
                cdict["tide_window_required"] = str(val).strip().lower() if str(val).strip().lower() in ["slack","slackhw"] else False
            # add more constraints as needed
        constraints_map[cid] = cdict
    activities = []
    for _, row in act_df.iterrows():
        preds = []
        pred_str = row.get("Predecessor ID(s)", "")
        if pd.notna(pred_str) and pred_str != "-":
            preds = [p.strip() for p in pred_str.split(",")]
        cid = row.get("Constraint_ID")
        constraints = constraints_map.get(cid, {})
        activities.append(Activity(
            id=row["ID"],
            name=row["Name"],
            description=row.get("Sub Activity", ""),
            predecessors=preds,
            duration=row["Duration (hours)"],
            group=row["Group"],
            constraints=constraints
        ))
    return activities
