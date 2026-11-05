"""Server side time limit for timed exams.

edx-proctoring closes an attempt when the browser timer asks it to, or lazily when something reads the attempt, and
the XBlock handlers never look at the attempt. Answers sent after the time ended are therefore accepted and graded.
This module refuses them at the one route every answer type goes through.

The rule ships behind a waffle switch and starts LOG-ONLY: while the switch is off, a late answer is logged as
`would_deny` and served as before. Once it is on (Django admin > Waffle > Switches, no deploy), it is logged as `deny`,
the attempt is closed and the answer is refused.

Any failure inside the check lets the answer through: a bug here must not stop learners answering their exams.

functions:
    refuse_late_answer: Return the refusal for a late exam answer, or None to let the request through.
"""
import logging
from datetime import datetime, timedelta, timezone

from django.http import JsonResponse
from django.utils.translation import gettext as _
from edx_toggles.toggles import WaffleSwitch
from opaque_keys.edx.keys import CourseKey, UsageKey
from rest_framework.exceptions import APIException

from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.edxapp_wrapper.proctoring import (
    HANDLER_AUTHENTICATORS,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
    get_current_exam_attempt,
    has_access,
)

logger = logging.getLogger(__name__)

# .. toggle_name: eox_nelp.enforce_exam_time_limit
# .. toggle_implementation: WaffleSwitch
# .. toggle_default: False
# .. toggle_description: When on, answers sent to a timed exam after the learner's attempt ended are refused with a
#   403 and the attempt is closed. When off, they are only logged (`exam_time_limit would_deny`).
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2026-11-05
# .. toggle_target_removal_date: 2027-03-31
ENFORCE_EXAM_TIME_LIMIT = WaffleSwitch("eox_nelp.enforce_exam_time_limit", __name__)

# The browser timer submits about 5 seconds after zero; this also leaves room for a request already on its way.
ALLOWANCE_SECONDS = 10

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# Handlers that never change an answer, so they stay open for reviewing a closed exam. Anything not listed is refused.
READ_ONLY_HANDLERS = frozenset({
    # Navigation, completion and tracking.
    "get_completion", "goto_position", "publish_completion", "publish_event", "student_view_user_state",
    # ORA screens and data. peer_assess and submit_feedback are about others' work and the grade, not the answer,
    # and may legitimately happen after the exam.
    "check_released", "download_url", "get_block_info", "get_learner_data", "get_rubric", "peer_assess",
    "render_grade", "render_leaderboard", "render_message", "render_peer_assessment", "render_self_assessment",
    "render_student_training", "render_submission", "submit_feedback", "waiting_step_data",
    # Poll and survey results.
    "get_results", "load_answers", "load_questions", "student_voted",
    # Drag and drop.
    "expand_static_url", "show_answer",
    # SCORM.
    "assets_proxy", "scorm_get_student_state", "scorm_get_value",
})

# The problem and video blocks route every action through this handler, with the action as its suffix.
SUFFIX_HANDLER = "xmodule_handler"
READ_ONLY_SUFFIXES = frozenset({"hint_button", "problem_get", "problem_show", "save_user_state"})
# handle_ajax runs these whatever the HTTP method is, so a GET can spend an attempt too.
ANSWER_SUFFIXES = frozenset({"problem_check", "problem_reset", "problem_save"})


def _can_change_an_answer(method, handler, suffix):
    """Tell whether this handler call may change an answer."""
    if handler == SUFFIX_HANDLER:
        if suffix in ANSWER_SUFFIXES:
            return True
        return method not in SAFE_METHODS and suffix not in READ_ONLY_SUFFIXES

    return method not in SAFE_METHODS and handler not in READ_ONLY_HANDLERS


def _get_user(request):
    """Return the caller, trying what the handler view tries for a request without a session (mobile, JWT)."""
    user = getattr(request, "user", None)

    if user and user.is_authenticated:
        return user

    for authenticator in HANDLER_AUTHENTICATORS:
        try:
            user_auth_tuple = authenticator().authenticate(request)
        except APIException:
            continue

        if user_auth_tuple is not None:
            return user_auth_tuple[0]

    return None


def _get_started_attempts(user, course_key):
    """Return the user's started attempts on the active exams of the course, as dictionaries."""
    return list(
        ProctoredExamStudentAttempt.objects.filter(
            user_id=user.id,
            proctored_exam__course_id=str(course_key),
            proctored_exam__is_active=True,
            started_at__isnull=False,
        ).values(
            "proctored_exam_id", "proctored_exam__content_id", "status", "started_at", "allowed_time_limit_mins",
        )
    )


def _get_sequence_block_id(usage_key):
    """Return the block id of the subsection holding this block, or None when it is not inside one."""
    block = modulestore().get_item(usage_key)

    while block is not None and block.category != "sequential":
        block = block.get_parent()

    return block.location.block_id if block is not None else None


def _find_attempt_for_block(attempts, usage_key):
    """Return the attempt whose exam holds this block, or None."""
    sequence_block_id = _get_sequence_block_id(usage_key)

    for attempt in attempts:
        if UsageKey.from_string(attempt["proctored_exam__content_id"]).block_id == sequence_block_id:
            return attempt

    return None


def _seconds_past_end(attempt):
    """Return how many seconds ago the attempt's time ended (negative while there is time left)."""
    expires_at = attempt["started_at"] + timedelta(minutes=attempt["allowed_time_limit_mins"])

    return (datetime.now(timezone.utc) - expires_at).total_seconds()


def _has_ended(attempt):
    """Tell whether the attempt is over: already closed, or still open and past its time plus the allowance."""
    if ProctoredExamStudentAttemptStatus.is_completed_status(attempt["status"]):
        return True

    return (
        ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt["status"])
        and _seconds_past_end(attempt) > ALLOWANCE_SECONDS
    )


def _close_attempt(attempt, user):
    """Close a still-open expired attempt. Reading it through edx-proctoring runs its own timeout."""
    if not ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt["status"]):
        return

    try:
        get_current_exam_attempt(attempt["proctored_exam_id"], user.id)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("exam_time_limit could not close the attempt of user_id=%s", user.id)


def _build_refusal(handler, suffix):
    """Return the refusal in the shape the block's own code can show to the learner."""
    message = _("The time for this exam has ended, so this answer was not saved.")

    # The problem block ignores a failed call on these actions; it reports a closed problem as a 200 with the text.
    if handler == SUFFIX_HANDLER and suffix == "problem_check":
        return JsonResponse({"success": message})

    if handler == SUFFIX_HANDLER and suffix in ANSWER_SUFFIXES:
        return JsonResponse({"success": False, "msg": message})

    return JsonResponse({"success": message}, status=403)


def _check_late_answer(request, view_kwargs):
    """Apply the rule to a handler call that may change an answer. Return the refusal or None."""
    user = _get_user(request)

    if user is None:
        return None

    course_key = CourseKey.from_string(view_kwargs["course_id"])
    attempts = _get_started_attempts(user, course_key)

    if not attempts:
        return None

    usage_key = UsageKey.from_string(view_kwargs["usage_id"]).map_into_course(course_key)
    attempt = _find_attempt_for_block(attempts, usage_key)

    if attempt is None or not _has_ended(attempt):
        return None

    log_context = (
        user.id, course_key, usage_key.block_id, view_kwargs["handler"], view_kwargs.get("suffix"),
        int(_seconds_past_end(attempt)),
    )

    if has_access(user, "staff", course_key):
        logger.info("exam_time_limit staff user_id=%s course=%s block=%s handler=%s/%s past_end_s=%s", *log_context)
        return None

    if not ENFORCE_EXAM_TIME_LIMIT.is_enabled():
        logger.warning(
            "exam_time_limit would_deny user_id=%s course=%s block=%s handler=%s/%s past_end_s=%s", *log_context,
        )
        return None

    logger.warning("exam_time_limit deny user_id=%s course=%s block=%s handler=%s/%s past_end_s=%s", *log_context)
    _close_attempt(attempt, user)

    return _build_refusal(view_kwargs["handler"], view_kwargs.get("suffix"))


def refuse_late_answer(request, view_kwargs):
    """Return the refusal for a late exam answer, or None to let the request through.

    Args:
        request: The Django request.
        view_kwargs: The keyword arguments of the xblock_handler route.

    Returns:
        JsonResponse or None.
    """
    if not _can_change_an_answer(request.method, view_kwargs["handler"], view_kwargs.get("suffix")):
        return None

    try:
        return _check_late_answer(request, view_kwargs)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("exam_time_limit check failed for %s", request.path_info)
        return None
