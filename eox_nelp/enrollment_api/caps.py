"""Request-size and per-caller hourly caps (decision a1-mail-cap), counted on the Django cache.

Hourly window: one counter per (caller, calendar hour), created with a TTL slightly longer than
the hour. The count is added atomically (`cache.incr`) and handed back when the request is
rejected, so a rejected call spends nothing. It is only as shared as the configured cache:
a per-process cache (LocMem) would count per process.
"""
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

KEY_TEMPLATE = "eox_nelp:enrollment_api:items:{caller}:{hour}"
WINDOW_SECONDS = 3600 + 300  # one hour plus slack so the counter outlives its bucket


class OverCap(ValidationError):
    """The request holds more items than allowed (400, whole request rejected)."""


class HourlyCapExceeded(APIException):
    """The caller is over its hourly item quota (429, whole request rejected)."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Hourly enrollment limit exceeded for this caller."
    default_code = "hourly_cap_exceeded"


def quota_key(caller, now=None):
    """Cache key for the caller's current hour bucket."""
    now = now or datetime.now(timezone.utc)
    return KEY_TEMPLATE.format(caller=caller, hour=now.strftime("%Y%m%d%H"))


def check_caps(caller, item_count):
    """Reject the request when it is too big or the caller is over the hourly quota.

    Raises:
        OverCap: more than EOX_NELP_ENROLLMENT_MAX_ITEMS items in the request.
        HourlyCapExceeded: the hourly total would pass EOX_NELP_ENROLLMENT_HOURLY_LIMIT.
    """
    max_items = getattr(settings, "EOX_NELP_ENROLLMENT_MAX_ITEMS", 100)
    hourly_limit = getattr(settings, "EOX_NELP_ENROLLMENT_HOURLY_LIMIT", 1000)
    if item_count > max_items:
        raise OverCap(f"Too many items in one request: {item_count} (maximum {max_items}).")
    key = quota_key(caller)
    cache.add(key, 0, WINDOW_SECONDS)
    if cache.incr(key, item_count) > hourly_limit:
        cache.decr(key, item_count)
        raise HourlyCapExceeded(f"Hourly enrollment limit of {hourly_limit} items exceeded for this caller.")
