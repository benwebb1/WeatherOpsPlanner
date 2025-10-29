import pandas as pd
from datetime import datetime, timedelta

class Activity:
    def __init__(self, id, name, description, predecessors, duration, group, constraints=None):
        self.id = id
        self.name = name
        self.description = description
        self.predecessors = predecessors
        self.duration = duration
        self.group = group
        self.constraints = constraints or {}
        self.start = None
        self.end = None
        self.successors = []
        self.earliest_start = None
        self.latest_end = None
        self.float = None

class Scheduler:
    def __init__(self, activities, daylight_windows=None, hw_tide_windows=None, lw_tide_windows=None):
        self.activities = activities
        self.daylight_windows = daylight_windows if daylight_windows else []
        self.tide_windows = {'HW': hw_tide_windows or [], 'LW': lw_tide_windows or []}
        self.activity_map = {act.id: act for act in activities}
        for act in self.activities:
            act.successors = []
        for act in self.activities:
            for pred_id in act.predecessors:
                if pred_id in self.activity_map:
                    self.activity_map[pred_id].successors.append(act.id)

    def find_aligned_start(self, activity, earliest_start):
        duration_td = timedelta(hours=activity.duration)
        tide_req = activity.constraints.get('tide_window_required', False)
        daylight_req = activity.constraints.get('daylight_required', False)

        def overlaps_daylight(start):
            end = start + duration_td
            return any((min(dl_end, end) - max(dl_start, start)).total_seconds() > 0 for dl_start, dl_end in self.daylight_windows)

        if tide_req:
            windows = []
            if tide_req == 'slackhw':
                windows = self.tide_windows['HW']
            elif tide_req == 'slack':
                windows = self.tide_windows['HW'] + self.tide_windows['LW']
            windows = sorted(windows, key=lambda w: w[0] + (w[1] - w[0]) / 2)
            for w_start, w_end in windows:
                window_center = w_start + (w_end - w_start) / 2
                proposed_start = window_center - duration_td / 2
                if proposed_start >= earliest_start:
                    if not daylight_req or overlaps_daylight(proposed_start):
                        return proposed_start
        if daylight_req:
            for dl_start, dl_end in self.daylight_windows:
                if dl_start >= earliest_start and (dl_end - dl_start) >= duration_td:
                    return dl_start
        return earliest_start

    def find_latest_aligned_start(self, activity, latest_end):
        duration_td = timedelta(hours=activity.duration)
        latest_start = latest_end - duration_td
        tide_req = activity.constraints.get('tide_window_required', False)
        daylight_req = activity.constraints.get('daylight_required', False)

        def overlaps_daylight(start):
            end = start + duration_td
            return any((min(dl_end, end) - max(dl_start, start)).total_seconds() > 0 for dl_start, dl_end in self.daylight_windows)

        if tide_req:
            windows = []
            if tide_req == 'slackhw':
                windows = self.tide_windows['HW']
            elif tide_req == 'slack':
                windows = self.tide_windows['HW'] + self.tide_windows['LW']
            windows = sorted(windows, key=lambda w: w[1], reverse=True)
            for w_start, w_end in windows:
                window_end = min(w_end, latest_end)
                window_start = window_end - duration_td
                if window_start >= w_start and window_start >= datetime.min:
                    if window_start <= latest_start:
                        if not daylight_req or overlaps_daylight(window_start):
                            return window_start
        if daylight_req:
            for dl_start, dl_end in sorted(self.daylight_windows, key=lambda w: w[1], reverse=True):
                window_end = min(dl_end, latest_end)
                window_start = window_end - duration_td
                if window_start >= dl_start and window_start >= datetime.min:
                    if window_start <= latest_start:
                        return window_start
        return latest_start

    def compute_start_end_forward(self, activity):
        if activity.predecessors:
            for pred_id in activity.predecessors:
                pred = self.activity_map[pred_id]
                if pred.end is None:
                    self.compute_start_end_forward(pred)
            earliest_start = max(self.activity_map[pred_id].end for pred_id in activity.predecessors)
        else:
            earliest_start = activity.start if activity.start else datetime.min
        activity.earliest_start = earliest_start
        activity.start = self.find_aligned_start(activity, earliest_start)
        activity.end = activity.start + timedelta(hours=activity.duration)
        activity.start = activity.start.replace(second=0, microsecond=0)
        activity.end = activity.end.replace(second=0, microsecond=0)

    def compute_start_end_latest(self, activity, latest_end=None):
        # If latest_end is not provided, infer it from successors or use project end
        if latest_end is None:
            successor_starts = [
                self.activity_map[succ_id].start
                for succ_id in activity.successors
                if self.activity_map[succ_id].start is not None
            ]
            if successor_starts:
                latest_end = min(successor_starts)
            else:
                # Use the latest scheduled end among all activities as the project end
                scheduled_ends = [a.end for a in self.activities if a.end is not None]
                if scheduled_ends:
                    latest_end = max(scheduled_ends)
                else:
                    latest_end = datetime.now()  # fallback if nothing is scheduled yet
        activity.latest_end = latest_end
        activity.start = self.find_latest_aligned_start(activity, latest_end)
        activity.end = activity.start + timedelta(hours=activity.duration)
        activity.start = activity.start.replace(second=0, microsecond=0)
        activity.end = activity.end.replace(second=0, microsecond=0)

    def schedule_around_target(self, target_name, target_start_time):
        for act in self.activities:
            act.start = None
            act.end = None
            act.earliest_start = None
            act.latest_end = None
            act.float = None

        target_act = next((a for a in self.activities if a.name == target_name), None)
        if not target_act:
            raise ValueError(f"Target activity '{target_name}' not found.")

        target_act.start = target_start_time.replace(second=0, microsecond=0)
        target_act.end = (target_act.start + timedelta(hours=target_act.duration)).replace(second=0, microsecond=0)

        pred_chain_ids = self.get_predecessor_chain(target_act)
        def schedule_chain_backward(act, latest_end):
            self.compute_start_end_latest(act, latest_end)
            for pred_id in act.predecessors:
                pred = self.activity_map[pred_id]
                schedule_chain_backward(pred, act.start)
        for pred_id in target_act.predecessors:
            pred = self.activity_map[pred_id]
            schedule_chain_backward(pred, target_act.start)

        succ_chain_ids = self.get_successor_chain(target_act)
        def schedule_chain_forward(act):
            if act.predecessors:
                for pred_id in act.predecessors:
                    pred = self.activity_map[pred_id]
                    if pred.end is None:
                        self.compute_start_end_forward(pred)
                earliest_start = max(self.activity_map[pred_id].end for pred_id in act.predecessors)
            else:
                earliest_start = act.start if act.start else target_act.end
            self.compute_start_end_forward(act)
            for succ_id in act.successors:
                succ = self.activity_map[succ_id]
                schedule_chain_forward(succ)
        for succ_id in target_act.successors:
            succ = self.activity_map[succ_id]
            schedule_chain_forward(succ)

        # Forward pass for all unscheduled activities
        for act in self.activities:
            if act.start is None or act.end is None:
                self.compute_start_end_forward(act)

        # Backward pass for all activities to set latest_end correctly
        for act in self.activities:
            if act.latest_end is None:
                self.compute_start_end_latest(act)

        # Calculate float
        for act in self.activities:
            if act.earliest_start and act.latest_end:
                act.float = (act.latest_end - act.earliest_start).total_seconds() / 3600 - act.duration

        return self.activities

    def get_predecessor_chain(self, target_act):
        chain = set()
        def recurse(act):
            for pred_id in act.predecessors:
                if pred_id not in chain:
                    chain.add(pred_id)
                    recurse(self.activity_map[pred_id])
        recurse(target_act)
        return chain

    def get_successor_chain(self, target_act):
        chain = set()
        def recurse(act):
            for succ_id in act.successors:
                if succ_id not in chain:
                    chain.add(succ_id)
                    recurse(self.activity_map[succ_id])
        recurse(target_act)
        return chain

    def to_dataframe(self):
        return pd.DataFrame([{
            "ID": a.id,
            "Name": a.name,
            "Start": a.start,
            "End": a.end,
            "Duration": a.duration,
            "Group": a.group,
            "Description": a.description,
            "Predecessor IDs": ", ".join(a.predecessors),
            "Successor IDs": ", ".join(a.successors),
            "Constraints": a.constraints,
            "Earliest Start": a.earliest_start,
            "Latest End": a.latest_end,
            "Float (hours)": a.float
        } for a in self.activities])

def generate_activity_list(act_df, constraints_df):
    constraints_map = {}
    for _, row in constraints_df.iterrows():
        cid = row.get("Constraint_ID")
        if pd.isna(cid):
            continue
        cdict = {}
        for col in row.index:
            val = row[col]
            if "Daylight" in col:
                cdict["daylight_required"] = bool(str(val).strip().lower() in ["yes", "y", "true", "1"])
            elif "Tidal Window" in col:
                cdict["tide_window_required"] = str(val).strip().lower() if str(val).strip().lower() in ["slack", "slackhw"] else False
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