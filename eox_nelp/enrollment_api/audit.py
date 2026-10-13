"""Structured `enrollment_api_result` events.

One logfmt line per enrollment item (`key=value` pairs, values never contain spaces) so a
GCP log-based alert can match on plain text, e.g. `enrollment_api_result` AND `email_result=failed`.
The same pairs are also passed as `extra` for JSON formatters. Raw email, national ID and
names are never logged: the person is `user_ref`, a salted HMAC of the lowercased email.
"""
import hashlib
import hmac
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("eox_nelp.enrollment_api")

# Field order of the line; see the ticket comment for the meaning of each.
FIELDS = (
    "request_id", "course_id", "mode", "caller_app", "site", "batch_index", "outcome", "reason",
    "email_template", "email_attempted", "email_result", "email_ms", "user_ref",
)


def user_ref(email):
    """Salted HMAC-SHA256 (first 16 hex) of the lowercased email; stable per person, not reversible."""
    salt = getattr(settings, "EOX_NELP_ENROLLMENT_LOG_SALT", None)
    if not salt:
        raise ImproperlyConfigured("EOX_NELP_ENROLLMENT_LOG_SALT must be set to use the enrollment API.")
    return hmac.new(salt.encode(), (email or "").strip().lower().encode(), hashlib.sha256).hexdigest()[:16]


def log_event(event="enrollment_api_result", level=logging.INFO, **fields):
    """Emit one event; absent fields render as `-`."""
    pairs = {name: fields.get(name) for name in FIELDS}
    pairs = {name: "-" if value in (None, "") else str(value).replace(" ", "_") for name, value in pairs.items()}
    line = " ".join(f"{name}={value}" for name, value in pairs.items())
    logger.log(level, "%s %s", event, line, extra={"event": event, **pairs})
