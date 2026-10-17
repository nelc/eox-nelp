"""Who gets the timed learner e-mails (Message 3 "learning starts", Message 5 "completion reminder") and when.

The rules live here as small pure predicates (easy to test at their boundaries); the platform data
comes through the `learner_emails` wrapper, already narrowed by the bounds computed here.

Per-tenant settings, all read per course ORG (`get_value_for_org`), never from the ambient tenant:

    LEARNING_STARTS_EMAIL_ENABLED       true to send Message 3        (default: off)
    COMPLETION_REMINDER_EMAIL_ENABLED   true to send Message 5        (default: off)
    COMPLETION_REMINDER_PROGRESS_PERCENT   progress trigger, e.g. 70  (default: DEFAULT_PROGRESS_PERCENT)
    COMPLETION_REMINDER_END_WINDOW_DAYS    end-date trigger, e.g. [3, 7]  (default: DEFAULT_END_WINDOW_DAYS)

A switch counts only when it is exactly `true`. A threshold that is present but malformed is an error
for that org (it is skipped and logged): it is never replaced by the default.
"""
from datetime import timedelta

from eox_nelp.edxapp_wrapper.learner_emails import (
    find_courses_ending,
    find_running_courses,
    find_started_courses,
    iter_enrollments,
    iter_progress,
    list_orgs,
)
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.learner_emails.models import LEARNING_STARTS, REMINDER_END, REMINDER_PROGRESS, LearnerEmailLog

LEARNING_STARTS_FLAG = "LEARNING_STARTS_EMAIL_ENABLED"
COMPLETION_REMINDER_FLAG = "COMPLETION_REMINDER_EMAIL_ENABLED"
PROGRESS_KEY = "COMPLETION_REMINDER_PROGRESS_PERCENT"
END_WINDOW_KEY = "COMPLETION_REMINDER_END_WINDOW_DAYS"

# The business values (owner decision cr-journey-defaults): 70% progress, 3 to 7 days before the end.
DEFAULT_PROGRESS_PERCENT = 70
DEFAULT_END_WINDOW_DAYS = (3, 7)
# The command runs hourly and a missed run must not lose a course start, so a start is still "due"
# this long after it. The log table keeps every learner at one e-mail however often a course is seen.
LEARNING_STARTS_LOOKBACK = timedelta(hours=3)


class JourneyConfigError(ValueError):
    """A tenant set a reminder threshold that cannot be used."""


def is_enabled(org, flag):
    """True only when the tenant of the org set the switch to exactly `true` (default off)."""
    return configuration_helpers.get_value_for_org(org, flag, False) is True


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def reminder_thresholds(org):
    """Return (progress percent, (min days, max days before the end)) for the org's tenant.

    Raises:
        JourneyConfigError: When the tenant set a value that is not a usable threshold.
    """
    percent = configuration_helpers.get_value_for_org(org, PROGRESS_KEY, DEFAULT_PROGRESS_PERCENT)
    window = configuration_helpers.get_value_for_org(org, END_WINDOW_KEY, list(DEFAULT_END_WINDOW_DAYS))

    if not (_is_number(percent) and 0 < percent < 100):
        raise JourneyConfigError(f"{PROGRESS_KEY} must be a number between 0 and 100 (org={org})")

    if not (isinstance(window, (list, tuple)) and len(window) == 2 and all(_is_number(d) for d in window)
            and 0 <= window[0] < window[1]):
        raise JourneyConfigError(f"{END_WINDOW_KEY} must be [min, max] days with 0 <= min < max (org={org})")

    return percent, (window[0], window[1])


def learning_starts_due(start, now):
    """True when the course started at most LEARNING_STARTS_LOOKBACK ago (start == now counts)."""
    return start is not None and now - LEARNING_STARTS_LOOKBACK <= start <= now


def enrolled_before_start(created, start):
    """True when the enrolment was created before the start, so the learner never got Message 4."""
    return created is not None and created < start


def progress_due(percent, threshold_percent):
    """True when completion (0..1) is at or over the threshold and the course is not yet complete."""
    shown = round(percent * 100, 6)  # 0.29 * 100 is 28.999999999999996: compare the rounded value

    return threshold_percent <= shown < 100


def end_window_due(end, now, min_days, max_days):
    """True when the course end is between `min_days` and `max_days` away (both ends included)."""
    return end is not None and now + timedelta(days=min_days) <= end <= now + timedelta(days=max_days)


def _unsent(course_id, kind):
    """User ids that already have a log row of this kind for the course (one cheap indexed query)."""
    return set(LearnerEmailLog.objects.filter(  # pylint: disable=no-member
        course_id=course_id, kind=kind).values_list("user_id", flat=True))


def learning_starts_candidates(org, now):
    """Yield (user_id, course_id) to e-mail Message 3: enrolled BEFORE the start of a course that just started."""
    for course_id, _org, start, _end in find_started_courses(org, now - LEARNING_STARTS_LOOKBACK, now):
        if not learning_starts_due(start, now):
            continue
        sent = _unsent(course_id, LEARNING_STARTS)
        for user_id, created in iter_enrollments(course_id):
            if user_id not in sent and enrolled_before_start(created, start):
                yield user_id, course_id


def progress_candidates(org, now):
    """Yield (user_id, course_id) of active learners of running courses at/over the progress threshold."""
    percent_threshold, _window = reminder_thresholds(org)

    for course_id, _org, _start, _end in find_running_courses(org, now):
        sent = _unsent(course_id, REMINDER_PROGRESS)
        active = {user_id for user_id, _created in iter_enrollments(course_id)}
        for user_id, percent in iter_progress(course_id, percent_threshold / 100 - 1e-9):
            if user_id in active and user_id not in sent and progress_due(percent, percent_threshold):
                yield user_id, course_id


def end_window_candidates(org, now):
    """Yield (user_id, course_id) of active learners of courses ending inside the tenant's window."""
    _percent, (min_days, max_days) = reminder_thresholds(org)

    for course_id, _org, _start, end in find_courses_ending(
        org, now + timedelta(days=min_days), now + timedelta(days=max_days),
    ):
        if not end_window_due(end, now, min_days, max_days):
            continue
        sent = _unsent(course_id, REMINDER_END)
        for user_id, _created in iter_enrollments(course_id):
            if user_id not in sent:
                yield user_id, course_id


# (tenant switch, log kind, candidate selector): what the hourly command works through for every org.
JOBS = (
    (LEARNING_STARTS_FLAG, LEARNING_STARTS, learning_starts_candidates),
    (COMPLETION_REMINDER_FLAG, REMINDER_PROGRESS, progress_candidates),
    (COMPLETION_REMINDER_FLAG, REMINDER_END, end_window_candidates),
)


def iter_jobs(kinds=None, orgs=None, ignore_switch=False):
    """Yield (org, kind, selector) for every org whose tenant switched the e-mail on.

    Args:
        kinds: Only these log kinds (default all).
        orgs: Only these orgs (default every org that has courses).
        ignore_switch: Yield even for orgs whose switch is off: the backfill runs BEFORE the switch.
    """
    for org in orgs or list_orgs():
        for flag, kind, selector in JOBS:
            if (not kinds or kind in kinds) and (ignore_switch or is_enabled(org, flag)):
                yield org, kind, selector
