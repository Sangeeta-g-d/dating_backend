# timezone_utils.py

from datetime import datetime
import pytz

def format_to_ist(utc_datetime):
    """
    Convert a UTC datetime to IST and return a formatted string.
    If input is naive (no timezone), it is assumed to be UTC.
    """

    if utc_datetime is None:
        return None

    # Define timezones
    utc_tz = pytz.timezone('UTC')
    ist_tz = pytz.timezone('Asia/Kolkata')

    # Make the datetime timezone-aware (if naive)
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_tz.localize(utc_datetime)

    # Convert to IST
    ist_datetime = utc_datetime.astimezone(ist_tz)

    # Format as a human-readable string
    formatted = ist_datetime.strftime("%d %b %Y, %I:%M %p IST")
    return formatted
