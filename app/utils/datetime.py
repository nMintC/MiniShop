from datetime import datetime, timedelta, timezone

VIETNAM_TIMEZONE = timezone(timedelta(hours=7), name="ICT")


def vietnam_now() -> datetime:
    return datetime.now(VIETNAM_TIMEZONE)


def as_vietnam_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=VIETNAM_TIMEZONE)
    return value.astimezone(VIETNAM_TIMEZONE)