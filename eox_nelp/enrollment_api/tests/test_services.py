"""Tests for EnrollmentService: every outcome, idempotency, closed course, mail-on-change, log fields."""
# pylint: disable=no-member  # the mixin's setUp attaches the patched collaborators
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.exceptions import NotFound, ValidationError

from eox_nelp.enrollment_api.services import CallContext, EnrollmentClosed, EnrollmentService

MODULE = "eox_nelp.enrollment_api.services"
COURSE = "course-v1:Org+Course+Run"
EMAIL = "Person@Example.com"


def state(allowed=False, enrollment=False):
    """Stand-in for the EmailEnrollmentState enroll_email returns."""
    return Mock(allowed=allowed, enrollment=enrollment)


class ServiceTestMixin:
    """Patches the edx-platform wrapper functions and builds a service."""

    def setUp(self):  # pylint: disable=invalid-name
        """Patch collaborators; default: open course, no account, no previous state."""
        patches = {
            "enroll_email": patch(f"{MODULE}.enroll_email"),
            "overview": patch(f"{MODULE}.get_course_overview"),
            "active": patch(f"{MODULE}.is_actively_enrolled", return_value=False),
            "on_site": patch(f"{MODULE}.user_on_site", return_value=True),
            "exists": patch(f"{MODULE}.account_exists", return_value=False),
            "key": patch(f"{MODULE}.get_valid_course_key", side_effect=lambda course_id: course_id),
            "task": patch(f"{MODULE}.send_enrollment_mail"),
        }
        for name, patcher in patches.items():
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        self.overview.return_value = Mock(
            is_enrollment_open=Mock(return_value=True), has_ended=Mock(return_value=False),
        )
        self.enroll_email.return_value = (state(), state(allowed=True), None)
        self.user = Mock(email="person@example.com")
        self.find_user = Mock(side_effect=NotFound("no user"))
        self.enroll_account = Mock(return_value=[{"username": "person", "course_id": COURSE, "mode": "honor"}])
        self.service = EnrollmentService(CallContext("req1", "app-abc", 7, "tenant.example"), self.find_user,
                                         self.enroll_account)

    @staticmethod
    def item(**extra):
        """A validated item as eox-core's serializer produces it."""
        return {"email": EMAIL, "username": None, "course_id": COURSE, "mode": "honor", "force": False, **extra}

    def enroll(self, item, index=0):
        """Run one item, executing the on_commit callbacks."""
        with self.captureOnCommitCallbacks(execute=True):
            return self.service.enroll(item, index)


class ReserveTestCase(ServiceTestMixin, TestCase):
    """Unknown email."""

    def test_unknown_email_is_reserved_and_invited(self):
        """Reserve for the caller's open course; no username; auto_enroll; invitation queued."""
        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            data = self.enroll(self.item())

        self.assertEqual(data[0]["result"], "reserved")
        self.assertNotIn("username", data[0])
        self.enroll_email.assert_called_once_with(COURSE, EMAIL, auto_enroll=True, message_students=False)
        self.task.delay.assert_called_once()
        args = self.task.delay.call_args.args
        self.assertEqual(args[:5], ("allowed_enroll", EMAIL, COURSE, True, 7))
        self.assertIn("outcome=reserved", logs.output[0])
        self.assertIn("email_template=invitation", logs.output[0])
        self.assertIn("email_result=queued", logs.output[0])

    def test_repeat_reserve_is_idempotent_and_sends_no_second_mail(self):
        """CEA already there: same result, no mail."""
        self.enroll_email.return_value = (state(allowed=True), state(allowed=True), None)

        data = self.enroll(self.item())

        self.assertEqual(data[0]["result"], "reserved")
        self.task.delay.assert_not_called()

    def test_closed_course_rejected_without_reservation(self):
        """Enrollment window closed: item error, enroll_email never called."""
        self.overview.return_value.is_enrollment_open.return_value = False

        with self.assertRaisesMessage(EnrollmentClosed, "Enrollment closed"):
            self.enroll(self.item())

        self.enroll_email.assert_not_called()
        self.task.delay.assert_not_called()

    def test_ended_course_rejected(self):
        """Course ended: same error."""
        self.overview.return_value.has_ended.return_value = True

        with self.assertRaises(EnrollmentClosed):
            self.enroll(self.item())

    def test_force_skips_the_closed_check(self):
        """eox-core's `force` means skip business rules; the check is skipped too."""
        self.overview.return_value.is_enrollment_open.return_value = False

        data = self.enroll(self.item(force=True))

        self.assertEqual(data[0]["result"], "reserved")

    def test_unknown_username_keeps_the_not_found_error(self):
        """A username that does not resolve is never reserved."""
        with self.assertRaises(NotFound):
            self.enroll(self.item(username="ghost"))

        self.enroll_email.assert_not_called()

    def test_existing_account_filtered_out_by_site_is_not_reserved(self):
        """The lookup said not found but an account owns the email: keep today's error."""
        self.exists.return_value = True

        with self.assertRaises(NotFound):
            self.enroll(self.item())

        self.enroll_email.assert_not_called()

    def test_retired_email_is_rejected(self):
        """enroll_email silently ignores retired addresses: no CEA means no 'reserved'."""
        self.enroll_email.return_value = (state(), state(allowed=False), None)

        with self.assertRaises(ValidationError):
            self.enroll(self.item())

        self.task.delay.assert_not_called()

    def test_unknown_course_is_reported(self):
        """get_course_overview raises NotFound for a course that does not exist."""
        self.overview.side_effect = NotFound("Course not found")

        with self.assertRaises(NotFound):
            self.enroll(self.item())


class ExistingAccountTestCase(ServiceTestMixin, TestCase):
    """Account exists."""

    def setUp(self):
        """The lookup now finds the user."""
        super().setUp()
        self.find_user.side_effect = None
        self.find_user.return_value = self.user

    def test_new_enrollment_notifies_once(self):
        """none -> active: enrolled, notice queued."""
        data = self.enroll(self.item())

        self.assertEqual(data[0]["result"], "enrolled")
        self.enroll_account.assert_called_once()
        self.assertEqual(self.task.delay.call_args.args[:2], ("enrolled_enroll", "person@example.com"))

    def test_repeat_enrol_is_idempotent_without_mail(self):
        """active -> active: result enrolled, outcome already_enrolled, no mail."""
        self.active.return_value = True

        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            data = self.enroll(self.item())

        self.assertEqual(data[0]["result"], "enrolled")
        self.task.delay.assert_not_called()
        self.assertIn("outcome=already_enrolled", logs.output[0])
        self.assertIn("email_attempted=false", logs.output[0])

    def test_mode_only_change_sends_no_mail(self):
        """Already active, new mode: no mail (g2-mode-change-mail)."""
        self.active.return_value = True

        self.enroll(self.item(mode="verified"))

        self.task.delay.assert_not_called()

    def test_reactivation_notifies(self):
        """inactive -> active counts as a state change (not actively enrolled before)."""
        self.active.return_value = False

        self.enroll(self.item(is_active=True))

        self.task.delay.assert_called_once()

    def test_deactivation_sends_no_mail(self):
        """is_active false never notifies."""
        self.active.return_value = True

        self.enroll(self.item(is_active=False))

        self.task.delay.assert_not_called()

    def test_account_of_another_tenant_is_enrolled_and_flagged_in_the_log_only(self):
        """Cross-tenant: result stays 'enrolled'; the log says enrolled_cross_tenant; no tenant is named."""
        self.on_site.return_value = False

        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            data = self.enroll(self.item())

        self.assertEqual(data[0]["result"], "enrolled")
        self.assertNotIn("tenant", str(data))
        self.assertIn("outcome=enrolled_cross_tenant", logs.output[0])

    def test_eox_core_validation_messages_are_left_alone(self):
        """eox-core returns messages (e.g. bad mode) with 200 today: no result tag, no mail."""
        self.enroll_account.return_value = [{"username": None, "messages": ["Invalid mode given:x"]}]

        data = self.enroll(self.item())

        self.assertNotIn("result", data[0])
        self.task.delay.assert_not_called()

    def test_bundle_items_pass_through(self):
        """Program enrolment keeps eox-core's behaviour untouched."""
        self.find_user.side_effect = AssertionError("not looked up")

        data = self.enroll(self.item(bundle_id="abc", course_id=None))

        self.assertEqual(data, self.enroll_account.return_value)
        self.task.delay.assert_not_called()


class LogContractTestCase(ServiceTestMixin, TestCase):
    """The enrollment_api_result event."""

    def test_event_fields_and_no_pii(self):
        """All fields present; no raw email or local part anywhere in the line."""
        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            self.enroll(self.item(), index=3)

        line = logs.output[0]
        for field in ("request_id=req1", f"course_id={COURSE}", "mode=honor", "caller_app=app-abc",
                      "site=tenant.example", "batch_index=3", "outcome=reserved", "user_ref="):
            self.assertIn(field, line)
        self.assertNotIn("@", line)
        self.assertNotIn("person", line.lower())

    def test_reject_is_a_warning_with_the_exception_class_only(self):
        """Rejects log at WARNING with the class name, never the exception text (it may hold the email)."""
        self.find_user.side_effect = NotFound(f"No user found by {EMAIL}")
        self.exists.return_value = True

        with self.assertLogs("eox_nelp.enrollment_api", "WARNING") as logs:
            with self.assertRaises(NotFound):
                self.enroll(self.item())

        self.assertIn("outcome=rejected", logs.output[0])
        self.assertIn("reason=NotFound", logs.output[0])
        self.assertNotIn("example.com", logs.output[0])

    def test_unexpected_error_is_logged_with_stack_and_reraised(self):
        """Non-API exceptions are ERROR with traceback."""
        self.enroll_email.side_effect = RuntimeError("db down")

        with self.assertLogs("eox_nelp.enrollment_api", "ERROR") as logs:
            with self.assertRaises(RuntimeError):
                self.enroll(self.item())

        self.assertIn("Traceback", logs.output[0])
