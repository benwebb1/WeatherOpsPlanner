from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun

# Define Sizewell C location (latitude, longitude, timezone)
sizewell = LocationInfo("Sizewell", "England", "Europe/London", 52.198, 1.604)

def generate_daylight_windows(start_date, end_date):
    current_date = start_date
    daylight_windows = []

    while current_date <= end_date:
        s = sun(sizewell.observer, date=current_date, tzinfo=sizewell.timezone)
        sunrise = s['sunrise']
        sunset = s['sunset']
        daylight_windows.append((sunrise, sunset))
        current_date += timedelta(days=1)

    return daylight_windows

# Example usage: generate windows for October 2025
start = datetime(2025, 10, 1)
end = datetime(2025, 10, 31)

windows = generate_daylight_windows(start, end)
for sunrise, sunset in windows:
    print(f"Sunrise: {sunrise}, Sunset: {sunset}")
