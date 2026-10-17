"""Tests for the certificate-ready e-mail task."""
from types import SimpleNamespace

from celery.exceptions import Retry
from django.test import TestCase
from mock import MagicMock, patch
from opaque_keys.edx.keys import CourseKey

from eox_nelp.learner_emails.models import CERTIFICATE_READY, LearnerEmailLog
from eox_nelp.learner_emails.tasks import (
    EmailNotDeliveredError,
    deliver_certificate_ready,
    send_certificate_ready_email,
)
from eox_nelp.learner_emails.tenant import TenantNotResolvedError

MODULE = "eox_nelp.learner_emails.tasks"
COURSE_ID = "course-v1:KSU+CS101+2026"


class DeliverCertificateReadyTestCase(TestCase):
    """The delivery binds the tenant, claims the row once, resolves the language and sends."""

    def setUp(self):
        """Patch every platform piece; the log table is the real one."""
        names = {
            "bind": "bind_tenant_for_org", "site": "get_site_for_domain", "cert": "get_downloadable_certificate",
            "overview": "get_course_overview", "user_lang": "get_user_language", "send": "send_and_confirm",
            "root": "tenant_root_url", "url": "get_certificate_url", "emulate": "emulate_tenant_request",
            "base": "get_base_context", "recipient": "make_recipient", "user_model": "User",
        }
        self.mocks = {}
        for key, name in names.items():
            patcher = patch(f"{MODULE}.{name}")
            self.mocks[key] = patcher.start()
            self.addCleanup(patcher.stop)
        m = self.mocks
        m["bind"].return_value = "ksu.example.com"
        m["cert"].return_value = SimpleNamespace(course_id=CourseKey.from_string(COURSE_ID), verify_uuid="abc")
        m["overview"].return_value = SimpleNamespace(display_name="Cyber", language="fr")
        m["user_lang"].return_value = "ar"
        m["send"].return_value = True
        m["root"].return_value = "https://ksu.example.com/"
        m["url"].return_value = "/certificates/abc"
        m["base"].return_value = {"platform_name": "KSU"}
        m["emulate"].return_value.__enter__ = MagicMock()
        m["emulate"].return_value.__exit__ = MagicMock(return_value=False)
        self.user = SimpleNamespace(id=7, profile=SimpleNamespace(name="Sara"))
        m["user_model"].objects.select_related.return_value.get.return_value = self.user

    def _rows(self):
        return LearnerEmailLog.objects.filter(kind=CERTIFICATE_READY).count()  # pylint: disable=no-member

    def test_sends_once_with_tenant_values(self):
        """Tenant bound for the org, message in the course language, link on the tenant domain."""
        deliver_certificate_ready(7, COURSE_ID)

        self.mocks["bind"].assert_called_once_with("KSU")
        self.mocks["site"].assert_called_once_with("ksu.example.com")
        message = self.mocks["send"].call_args[0][0]
        self.assertEqual(message.language, "fr")
        self.assertEqual(message.context["certificate_url"], "https://ksu.example.com/certificates/abc")
        self.assertEqual(message.context["full_name"], "Sara")
        self.assertNotIn("course_ids", message.context)
        self.assertEqual(self._rows(), 1)

    def test_repeated_calls_send_one_email(self):
        """The unique log row makes the second call a no-op."""
        deliver_certificate_ready(7, COURSE_ID)
        deliver_certificate_ready(7, COURSE_ID)

        self.assertEqual(self.mocks["send"].call_count, 1)
        self.assertEqual(self._rows(), 1)

    def test_language_falls_to_the_learner_then_english(self):
        """No course language -> the learner's; neither -> English."""
        self.mocks["overview"].return_value = SimpleNamespace(display_name="Cyber", language=None)
        deliver_certificate_ready(7, COURSE_ID)
        self.assertEqual(self.mocks["send"].call_args[0][0].language, "ar")

        LearnerEmailLog.objects.all().delete()  # pylint: disable=no-member
        self.mocks["user_lang"].return_value = None
        deliver_certificate_ready(7, COURSE_ID)
        self.assertEqual(self.mocks["send"].call_args[0][0].language, "en")

    def test_no_downloadable_certificate_sends_nothing(self):
        """A certificate revoked before the task ran is not announced."""
        self.mocks["cert"].return_value = None

        deliver_certificate_ready(7, COURSE_ID)

        self.mocks["send"].assert_not_called()
        self.assertEqual(self._rows(), 0)

    def test_unresolved_tenant_fails_loudly_and_sends_nothing(self):
        """No tenant, no unbranded mail, and no log row is left behind."""
        self.mocks["bind"].side_effect = TenantNotResolvedError("x")

        with self.assertRaises(TenantNotResolvedError):
            deliver_certificate_ready(7, COURSE_ID)

        self.mocks["send"].assert_not_called()
        self.assertEqual(self._rows(), 0)

    def test_missing_site_fails_loudly(self):
        """A tenant domain with no Site row cannot be substituted by another host."""
        self.mocks["site"].side_effect = LookupError("no site")

        with self.assertRaises(LookupError):
            deliver_certificate_ready(7, COURSE_ID)

        self.mocks["send"].assert_not_called()

    def test_blank_learner_name_fails_loudly(self):
        """No name for the greeting: failure, not a silently different greeting."""
        self.user.profile.name = ""

        with self.assertRaises(ValueError):
            deliver_certificate_ready(7, COURSE_ID)

        self.mocks["send"].assert_not_called()

    def test_undelivered_mail_releases_the_claim(self):
        """When ACE does not confirm the delivery the row is removed so the retry can send."""
        self.mocks["send"].return_value = False

        with self.assertRaises(EmailNotDeliveredError):
            deliver_certificate_ready(7, COURSE_ID)

        self.assertEqual(self._rows(), 0)

    def test_task_retries_then_logs_an_error_without_pii(self):
        """Transient failure retries; the last failure is an ERROR line with ids and class only."""
        self.mocks["send"].return_value = False

        with patch.object(send_certificate_ready_email, "retry", side_effect=Retry()):
            with self.assertRaises(Retry):
                send_certificate_ready_email.apply(args=(7, COURSE_ID), throw=True)

        task = send_certificate_ready_email
        task.request.retries = task.max_retries
        with self.assertLogs(MODULE, level="ERROR") as logs:
            task.run(7, COURSE_ID)

        line = logs.output[0]
        self.assertIn("certificate_ready_email_failed user_id=7", line)
        self.assertIn("EmailNotDeliveredError", line)
        self.assertNotIn("@", line)
