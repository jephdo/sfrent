from datetime import date, datetime

import pytz


def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.

    http://flask.pocoo.org/snippets/33/
    """
    if not isinstance(dt, (datetime, date)):
        return dt
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    diff = now - dt

    periods = (
        (diff.days // 365, "year", "years"),
        (diff.days // 30, "month", "months"),
        (diff.days // 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds // 3600, "hour", "hours"),
        (diff.seconds // 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)
    return default


def format_pst(datetime):
    pst = pytz.timezone('US/Pacific')
    datetime_pst = datetime.astimezone(pst)
    return datetime_pst.strftime('%H:%M PST')


def format_date(datetime):
    pst = pytz.timezone('US/Pacific')
    datetime_pst = datetime.astimezone(pst)
    return datetime_pst.strftime('%b %d')