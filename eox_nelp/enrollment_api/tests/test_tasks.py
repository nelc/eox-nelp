"""Tests for the mail task: site context, retries, final failure logging."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase

from eox_nelp.enrollment_api import tasks

MODULE = "eox_nelp.enrollment_api.tasks"
LOG_FIELDS = {"request_id": "req1", "user_ref": "abc123", "batch_index": 0}


class SendEnrollmentMailTestCase(TestCase):
    """The queued mail carries the caller's site and fails safely."""

    def setUp(self):
        """A caller site and a registered user."""
        self.site = Site.objects.create(domain="tenant.example", name="tenant")
        get_user_model().objects.create(username="person", email="person@example.com")

    def run_task(self, message_type="enrolled_enroll"):
        """Run the task eagerly (retries run inline)."""
        return tasks.send_enrollment_mail.apply(
            args=(message_type, "person@example.com", "course-v1:Org+Course+Run", True, self.site.id, LOG_FIELDS),
        )

    @patch(f"{MODULE}.send_mail_to_student")
    @patch(f"{MODULE}.get_email_params", return_value={"site_name": "tenant.example"})
    @patch(f"{MODULE}.get_course_overview")
    @patch(f"{MODULE}.emulate_http_request")
    def test_mail_is_sent_inside_the_callers_site_context(self, emulate, _overview, _params, send):
        """The Site travels as an id and is emulated; params carry message type and address."""
        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            self.run_task()

        self.assertEqual(emulate.call_args.kwargs["site"], self.site)
        email, params = send.call_args.args
        self.assertEqual(email, "person@example.com")
        self.assertEqual(params["message_type"], "enrolled_enroll")
        self.assertEqual(params["email_address"], "person@example.com")
        self.assertIn("user_id", params)
        self.assertIn("email_result=sent", logs.output[0])
        self.assertIn("request_id=req1", logs.output[0])

    @patch(f"{MODULE}.send_mail_to_student")
    @patch(f"{MODULE}.get_email_params", return_value={})
    @patch(f"{MODULE}.get_course_overview")
    def test_invitation_has_no_user_fields(self, _overview, _params, send):
        """allowed_enroll (reserved email) adds no user_id/full_name."""
        self.run_task("allowed_enroll")

        self.assertNotIn("full_name", send.call_args.args[1])

    @patch(f"{MODULE}.RETRY_BASE_SECONDS", 0)
    @patch(f"{MODULE}.send_mail_to_student", side_effect=OSError("550 person@example.com rejected"))
    @patch(f"{MODULE}.get_email_params", return_value={})
    @patch(f"{MODULE}.get_course_overview")
    def test_transient_failure_retries_then_logs_final_failure_without_text(self, _overview, _params, send):
        """1 try + 3 retries, then WARNING with the exception class only; the task itself succeeds."""
        with self.assertLogs("eox_nelp.enrollment_api", "WARNING") as logs:
            result = self.run_task()

        self.assertEqual(send.call_count, tasks.MAIL_MAX_RETRIES + 1)
        self.assertTrue(result.successful())
        self.assertEqual(len(logs.output), 1)
        self.assertIn("email_result=failed:OSError", logs.output[0])
        self.assertNotIn("example.com", logs.output[0])

    @patch(f"{MODULE}.RETRY_BASE_SECONDS", 0)
    @patch(f"{MODULE}.send_mail_to_student", side_effect=[OSError("x"), None])
    @patch(f"{MODULE}.get_email_params", return_value={})
    @patch(f"{MODULE}.get_course_overview")
    def test_recovers_after_a_retry(self, _overview, _params, send):
        """A transient failure followed by success logs 'sent'."""
        with self.assertLogs("eox_nelp.enrollment_api", "INFO") as logs:
            self.run_task()

        self.assertEqual(send.call_count, 2)
        self.assertIn("email_result=sent", logs.output[-1])
