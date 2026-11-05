"""
Test the server side time limit for timed exams.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from ddt import data, ddt, unpack

from eox_nelp import exam_time_limit
from eox_nelp.exam_time_limit import refuse_late_answer

COURSE_ID = "course-v1:org+course+run"
EXAM_BLOCK_ID = "exam"
USAGE_ID = "block-v1:org+course+run+type@problem+block@answer"
INCOMPLETE = ("started", "ready_to_submit")
COMPLETED = ("submitted", "timed_out")


def build_attempt(status="started", minutes_ago=60, allowed=30):
    """Return an attempt row as _get_started_attempts gives it."""
    return {
        "proctored_exam_id": 7,
        "proctored_exam__content_id": f"block-v1:org+course+run+type@sequential+block@{EXAM_BLOCK_ID}",
        "status": status,
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        "allowed_time_limit_mins": allowed,
    }


def build_request(method="POST"):
    """Return a request of a learner with a session."""
    return Mock(method=method, path_info="/handler", user=Mock(id=5, is_authenticated=True))


def build_kwargs(handler="xmodule_handler", suffix="problem_check"):
    """Return the keyword arguments of the xblock_handler route."""
    return {"course_id": COURSE_ID, "usage_id": USAGE_ID, "handler": handler, "suffix": suffix}


@ddt
class RefuseLateAnswerTestCase(TestCase):
    """Test refuse_late_answer."""

    def setUp(self):
        """Set up the platform dependencies: an expired open attempt on the exam holding the block, switch on."""
        self.attempt_model = self._start_patch("ProctoredExamStudentAttempt")
        self.attempt_model.objects.filter.return_value.values.return_value = [build_attempt()]

        status = self._start_patch("ProctoredExamStudentAttemptStatus")
        status.is_completed_status.side_effect = lambda value: value in COMPLETED
        status.is_incomplete_status.side_effect = lambda value: value in INCOMPLETE

        self.has_access = self._start_patch("has_access", return_value=False)
        self.close = self._start_patch("get_current_exam_attempt")
        self.switch = self._start_patch("ENFORCE_EXAM_TIME_LIMIT")
        self.switch.is_enabled.return_value = True

        sequence = Mock(category="sequential", location=Mock(block_id=EXAM_BLOCK_ID))
        unit = Mock(category="vertical", get_parent=Mock(return_value=sequence))
        problem = Mock(category="problem", get_parent=Mock(return_value=unit))
        self.modulestore = self._start_patch("modulestore")
        self.modulestore.return_value.get_item.return_value = problem

    def _start_patch(self, name, **kwargs):
        """Patch a name in the module for the whole test."""
        patcher = patch.object(exam_time_limit, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _set_attempts(self, *attempts):
        """Set the attempts the learner has in the course."""
        self.attempt_model.objects.filter.return_value.values.return_value = list(attempts)

    def test_late_problem_check_is_refused_and_attempt_closed(self):
        """
        A late problem answer, switch on.
        Expected behavior:
            - Response is a 200 with the message as `success`, which the problem block shows to the learner.
            - The attempt is closed through edx-proctoring.
        """
        response = refuse_late_answer(build_request(), build_kwargs())

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(json.loads(response.content)["success"], str)
        self.close.assert_called_once_with(7, 5)

    @data("problem_save", "problem_reset")
    def test_late_problem_save_and_reset_are_refused(self, suffix):
        """
        The other problem actions, switch on.
        Expected behavior:
            - Response is a 200 with success False and the message as `msg`, which the problem block shows.
        """
        response = refuse_late_answer(build_request(), build_kwargs(suffix=suffix))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])
        self.assertIn("msg", json.loads(response.content))

    @data(("submit", None), ("save_submission", None), ("vote", None), ("drop_item", None), ("scorm_set_values", None))
    @unpack
    def test_other_answer_types_are_refused(self, handler, suffix):
        """
        A late answer through a handler that is not on the read-only list (ORA, poll, drag and drop, SCORM).
        Expected behavior:
            - Response is a 403.
        """
        response = refuse_late_answer(build_request(), build_kwargs(handler=handler, suffix=suffix))

        self.assertEqual(response.status_code, 403)

    def test_get_that_spends_an_attempt_is_refused(self):
        """
        handle_ajax runs problem_check for any HTTP method.
        Expected behavior:
            - A GET to problem_check is refused too.
        """
        response = refuse_late_answer(build_request(method="GET"), build_kwargs())

        self.assertIsInstance(json.loads(response.content)["success"], str)

    @data(
        ("POST", "xmodule_handler", "problem_get"),
        ("POST", "xmodule_handler", "problem_show"),
        ("POST", "xmodule_handler", "save_user_state"),
        ("POST", "render_submission", None),
        ("POST", "publish_completion", None),
        ("POST", "peer_assess", None),
        ("GET", "submit", None),
        ("GET", "xmodule_handler", "problem_get"),
    )
    @unpack
    def test_calls_that_cannot_change_an_answer_pass_without_a_query(self, method, handler, suffix):
        """
        Reads and non-answer calls, so reviewing a closed exam keeps working.
        Expected behavior:
            - The request passes and no attempt is even looked up.
        """
        response = refuse_late_answer(build_request(method=method), build_kwargs(handler=handler, suffix=suffix))

        self.assertIsNone(response)
        self.attempt_model.objects.filter.assert_not_called()

    def test_switch_off_only_logs(self):
        """
        Late answer with the switch off.
        Expected behavior:
            - The request passes, is logged as would_deny and the attempt is not closed.
        """
        self.switch.is_enabled.return_value = False

        with self.assertLogs(exam_time_limit.logger, "WARNING") as logs:
            response = refuse_late_answer(build_request(), build_kwargs())

        self.assertIsNone(response)
        self.assertIn("would_deny", logs.output[0])
        self.close.assert_not_called()

    @data(
        ("started", 10),  # Time left.
        ("started", 30),  # Inside the allowance.
        ("ready_to_submit", 10),  # Reviewing before submitting.
        ("ready_to_resume", 60),  # Waiting to resume.
    )
    @unpack
    def test_open_attempt_passes(self, status, minutes_ago):
        """
        Answers while the attempt is still running.
        Expected behavior:
            - The request passes.
        """
        self._set_attempts(build_attempt(status=status, minutes_ago=minutes_ago))

        self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_allowance_is_counted_from_the_learners_own_time(self):
        """
        A learner with an extra-time allowance, 40 minutes into a 30 minute exam with 60 allowed.
        Expected behavior:
            - The request passes.
        """
        self._set_attempts(build_attempt(minutes_ago=40, allowed=60))

        self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_past_the_allowance_is_refused(self):
        """
        An answer just past the 10 second allowance.
        Expected behavior:
            - The answer is refused.
        """
        attempt = build_attempt()
        attempt["started_at"] = datetime.now(timezone.utc) - timedelta(minutes=30, seconds=12)
        self._set_attempts(attempt)

        self.assertIsNotNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_submitted_attempt_is_refused_without_closing_again(self):
        """
        An answer after the learner already submitted, with time still on the clock.
        Expected behavior:
            - The answer is refused and edx-proctoring is not asked to close it.
        """
        self._set_attempts(build_attempt(status="submitted", minutes_ago=5))

        self.assertIsNotNone(refuse_late_answer(build_request(), build_kwargs()))
        self.close.assert_not_called()

    def test_no_attempt_in_the_course_passes_without_loading_the_block(self):
        """
        Most learners have no attempt in the course.
        Expected behavior:
            - The request passes and the modulestore is not touched.
        """
        self._set_attempts()

        self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))
        self.modulestore.assert_not_called()

    def test_block_outside_the_exam_passes(self):
        """
        An answer to a problem in another subsection of the course.
        Expected behavior:
            - The request passes.
        """
        other = Mock(category="sequential", location=Mock(block_id="other"))
        self.modulestore.return_value.get_item.return_value = other

        self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_block_with_no_subsection_passes(self):
        """
        A block whose parents end before reaching a subsection.
        Expected behavior:
            - The request passes.
        """
        self.modulestore.return_value.get_item.return_value = Mock(category="html", get_parent=Mock(return_value=None))

        self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_staff_pass_and_are_logged(self):
        """
        Course staff keep access to the content by design.
        Expected behavior:
            - The request passes, is logged and the attempt is not closed.
        """
        self.has_access.return_value = True

        with self.assertLogs(exam_time_limit.logger, "INFO") as logs:
            response = refuse_late_answer(build_request(), build_kwargs())

        self.assertIsNone(response)
        self.assertIn("staff", logs.output[0])
        self.close.assert_not_called()

    def test_failure_to_close_still_refuses(self):
        """
        edx-proctoring fails while closing the attempt.
        Expected behavior:
            - The late answer is still refused.
        """
        self.close.side_effect = ValueError("boom")

        with self.assertLogs(exam_time_limit.logger, "ERROR"):
            response = refuse_late_answer(build_request(), build_kwargs())

        self.assertIsNotNone(response)

    def test_failure_in_the_check_lets_the_answer_through(self):
        """
        Anything unexpected inside the check.
        Expected behavior:
            - The request passes and the failure is logged.
        """
        self.attempt_model.objects.filter.side_effect = ValueError("boom")

        with self.assertLogs(exam_time_limit.logger, "ERROR"):
            self.assertIsNone(refuse_late_answer(build_request(), build_kwargs()))

    def test_anonymous_without_token_passes(self):
        """
        A request with no session and no token: the handler view rejects it itself.
        Expected behavior:
            - The request passes and no attempt is looked up.
        """
        request = build_request()
        request.user.is_authenticated = False

        self.assertIsNone(refuse_late_answer(request, build_kwargs()))
        self.attempt_model.objects.filter.assert_not_called()

    def test_token_caller_is_checked_like_a_session(self):
        """
        A mobile or JWT caller: the handler view authenticates it after the middleware has run.
        Expected behavior:
            - The authenticator is tried, a failing one is skipped and the late answer is refused.
        """
        failing = Mock()
        failing.return_value.authenticate.side_effect = exam_time_limit.APIException()
        working = Mock()
        working.return_value.authenticate.return_value = (Mock(id=9, is_authenticated=True), "token")
        request = build_request()
        request.user.is_authenticated = False

        with patch.object(exam_time_limit, "HANDLER_AUTHENTICATORS", (failing, working)):
            response = refuse_late_answer(request, build_kwargs())

        self.assertIsNotNone(response)
        self.close.assert_called_once_with(7, 9)
