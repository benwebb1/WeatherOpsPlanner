from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import pandas as pd
from scipy.signal import find_peaks
import matplotlib.pyplot as plt

def get_daylight_windows(start_date, end_date, plot=False, save_csv=None):
    sizewell = LocationInfo("Sizewell", "England", "Europe/London", 52.198, 1.604)
    daylight_windows = []
    records = []
    current_date = start_date

    while current_date <= end_date:
        s = sun(sizewell.observer, date=current_date, tzinfo=sizewell.timezone)
        sunrise = s['sunrise']
        sunset = s['sunset']
        daylight_windows.append((sunrise, sunset))
        records.append({'Date': current_date.date(), 'Sunrise': sunrise, 'Sunset': sunset})
        current_date += timedelta(days=1)

    if save_csv:
        df = pd.DataFrame(records)
        df.to_csv(save_csv, index=False)

    return daylight_windows

def get_tide_windows(tidaldata_path,start_date=None,end_date=None,skiprows=2,datetime_col="DateTime",
                     height_col="Height",slack_window_before=1.5,slack_window_after=1.5,plot=False,save_csv=None):
    """
    Extracts high water (HW) and low water (LW) slack windows from tidal data.

    Args:
        tidaldata_path (str): Path to tidal CSV file.
        start_date (datetime or None): Filter data from this date (inclusive).
        end_date (datetime or None): Filter data up to this date (inclusive).
        skiprows (int): Number of header rows to skip in CSV.
        datetime_col (str): Name of the datetime column.
        height_col (str): Name of the tide height column.
        slack_window_before (float): Hours before HW/LW for window start.
        slack_window_after (float): Hours after HW/LW for window end.
        plot (bool): If True, plot tide curve and windows.
        save_csv (str or None): If provided, path to save CSV.

    Returns:
        hw_windows (list of tuples): [(slack_start, slack_end), ...] for HW.
        lw_windows (list of tuples): [(slack_start, slack_end), ...] for LW.
    """
    df = pd.read_csv(tidaldata_path, skiprows=skiprows, names=[datetime_col, height_col])
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors='coerce')
    df[height_col] = pd.to_numeric(df[height_col], errors='coerce')
    df.dropna(inplace=True)

    # Print loaded data info
    print(f"Loaded data from {df[datetime_col].min()} to {df[datetime_col].max()} with {len(df)} records.")

    # Filter by date if specified
    if start_date is not None:
        df = df[df[datetime_col] >= start_date]
    if end_date is not None:
        df = df[df[datetime_col] <= end_date]

    # Print filtered data info
    print(f"Filtered data from {df[datetime_col].min()} to {df[datetime_col].max()} with {len(df)} records.")

    # Find HW (peaks) and LW (troughs)
    peaks, _ = find_peaks(df[height_col])
    troughs, _ = find_peaks(-df[height_col])

    hw_times = df.iloc[peaks][[datetime_col, height_col]].copy()
    hw_times["Type"] = "HW"
    lw_times = df.iloc[troughs][[datetime_col, height_col]].copy()
    lw_times["Type"] = "LW"

    events = pd.concat([hw_times, lw_times]).sort_values(datetime_col).reset_index(drop=True)
    events["Slack Start"] = events[datetime_col] - pd.Timedelta(hours=slack_window_before)
    events["Slack End"] = events[datetime_col] + pd.Timedelta(hours=slack_window_after)

    hw_windows = [(row["Slack Start"], row["Slack End"]) for _, row in events[events["Type"] == "HW"].iterrows()]
    lw_windows = [(row["Slack Start"], row["Slack End"]) for _, row in events[events["Type"] == "LW"].iterrows()]

    if plot:
        plt.figure(figsize=(15, 6))
        plt.plot(df[datetime_col], df[height_col], label="Tide Height", color='gray')
        plt.plot(hw_times[datetime_col], hw_times[height_col], "ro", label="High Water (HW)")
        plt.plot(lw_times[datetime_col], lw_times[height_col], "bo", label="Low Water (LW)")
        for _, row in events.iterrows():
            plt.axvspan(row["Slack Start"], row["Slack End"], color='green', alpha=0.2)
        plt.xlabel("DateTime")
        plt.ylabel("Height (m)")
        plt.title("Tidal Data with HW, LW, and Slack Water Windows")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    if save_csv:
        events.to_csv(save_csv, index=False)

    return hw_windows, lw_windows
