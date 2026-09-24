"""Minute boundaries shared by signal creation and historical tracking."""
from datetime import datetime, timedelta, timezone

MINUTE = timedelta(minutes=1)


def minute_ceiling(value: datetime) -> datetime:
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    floor = value.replace(second=0, microsecond=0)
    return floor if value == floor else floor + MINUTE
