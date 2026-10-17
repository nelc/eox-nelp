"""Tests for the receiver that queues the certificate-ready e-mail."""
from ddt import data, ddt
from django.test import TestCase
from mock import patch
from opaque_keys.edx.keys import CourseKey

from eox_nelp.signals.receivers import certificate_ready_email_publisher

MODULE = "eox_nelp.signals.receivers"
FLAG = "CERTIFICATE_READY_EMAIL_ENABLED"


def _certificate(status="downloadable", course="course-v1:KSU+CS101+2026"):
    """Minimal CertificateData stand-in."""
    from types import SimpleNamespace  # pylint: disable=import-outside-toplevel
    return SimpleNamespace(
        current_status=status,
        user=SimpleNamespace(id=7),
        course=SimpleNamespace(course_key=CourseKey.from_string(course)),
    )


@ddt
@patch(f"{MODULE}.send_certificate_ready_email")
@patch(f"{MODULE}.configuration_helpers")
class CertificateReadyReceiverTestCase(TestCase):
    """Only downloadable certificates of opted-in tenants are queued, after commit."""

    def _run(self, certificate):
        with self.captureOnCommitCallbacks(execute=True):
            certificate_ready_email_publisher(certificate=certificate, metadata=None)

    def test_queues_when_enabled(self, helpers_mock, task_mock):
        """Flag true for the org -> one task with ids only."""
        helpers_mock.get_value_for_org.return_value = True

        self._run(_certificate())

        helpers_mock.get_value_for_org.assert_called_once_with("KSU", FLAG, False)
        task_mock.delay.assert_called_once_with(user_id=7, course_id="course-v1:KSU+CS101+2026")

    @data("generating", "notpassing", "unavailable", "unverified", "invalidated")
    def test_ignores_other_statuses(self, status, helpers_mock, task_mock):
        """Only `downloadable` counts; the flag is not even read."""
        helpers_mock.get_value_for_org.return_value = True

        self._run(_certificate(status=status))

        task_mock.delay.assert_not_called()
        helpers_mock.get_value_for_org.assert_not_called()

    @data(False, None, "true", 1, "")
    def test_only_a_real_true_enables(self, value, helpers_mock, task_mock):
        """Off, unset or a non-boolean value (a string "false" is truthy!) queues nothing."""
        helpers_mock.get_value_for_org.return_value = value

        self._run(_certificate())

        task_mock.delay.assert_not_called()

    def test_flag_is_read_per_org(self, helpers_mock, task_mock):
        """Tenant A enabled and tenant B not: only A's certificate is queued."""
        helpers_mock.get_value_for_org.side_effect = lambda org, key, default: org == "KSU"

        self._run(_certificate(course="course-v1:OTHER+CS101+2026"))
        task_mock.delay.assert_not_called()

        self._run(_certificate(course="course-v1:KSU+CS101+2026"))
        task_mock.delay.assert_called_once()

    def test_not_queued_before_commit(self, helpers_mock, task_mock):
        """Inside an open transaction nothing is queued until it commits."""
        helpers_mock.get_value_for_org.return_value = True

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            certificate_ready_email_publisher(certificate=_certificate(), metadata=None)

        task_mock.delay.assert_not_called()
        self.assertEqual(len(callbacks), 1)
