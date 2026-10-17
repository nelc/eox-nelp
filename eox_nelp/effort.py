"""Format a course "Effort" value (free text typed by the course author) as a localized duration in hours.

Pure Python on purpose: the e-mail templates reach it through the `effort_hours` filter
(`{% load eox_nelp_tags %}`) and a Mako page (the R6 About page) can call it directly:

    <%! from eox_nelp.effort import format_effort_hours %>
    ${format_effort_hours(course.effort)}
"""
import re
from decimal import Decimal

from django.utils.translation import gettext as _
from django.utils.translation import ngettext

HH_MM = re.compile(r"^(\d+):([0-5]\d)$")
INTEGER = re.compile(r"^\d+$")
DECIMAL = re.compile(r"^\d+\.\d+$")
# Plural form used for a fractional count ("1.5 hours"): the "other" form of every language we ship.
FRACTION_PLURAL_COUNT = 100


def _hours_text(count, shown):
    """"<shown> hour(s)" with the plural form of `count`."""
    return ngettext("%(count)s hour", "%(count)s hours", count) % {"count": shown}


def _minutes_text(count):
    """"<count> minute(s)" with the plural form of `count`."""
    return ngettext("%(count)s minute", "%(count)s minutes", count) % {"count": count}


def _hhmm_text(hours, minutes):
    """Text of an "HH:MM" value: hours, plus minutes only when non-zero (minutes alone for "0:30")."""
    if not minutes:
        return _hours_text(hours, hours)
    if not hours:
        return _minutes_text(minutes)
    return _("%(hours)s and %(minutes)s") % {"hours": _hours_text(hours, hours), "minutes": _minutes_text(minutes)}


def format_effort_hours(effort):
    """Return the effort as a localized, pluralised duration; text that is not a number comes back as typed.

    Accepted forms (surrounding spaces ignored): "HH:MM" (hours, plus minutes only when non-zero),
    a whole number of hours ("4") and a decimal ("1.5"). A blank value gives "". Anything else
    ("about a week") is returned exactly as it was typed, never guessed at.
    """
    text = "" if effort is None else str(effort).strip()
    hhmm = HH_MM.match(text)
    result = str(effort) if text else ""

    if hhmm:
        result = _hhmm_text(int(hhmm.group(1)), int(hhmm.group(2)))
    elif INTEGER.match(text):
        result = _hours_text(int(text), int(text))
    elif DECIMAL.match(text):
        result = _hours_text(FRACTION_PLURAL_COUNT, Decimal(text).normalize())

    return result
