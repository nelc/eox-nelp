"""Tests for the backfill_certificate_ready_emails command."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from mock import patch

from eox_nelp.learner_emails.models import CERTIFICATE_READY, LearnerEmailLog

MODULE = "eox_nelp.management.commands.backfill_certificate_ready_emails"


class BackfillCertificateReadyEmailsTestCase(TestCase):
    """Dry run counts; --apply writes the rows once."""

    def _run(self, *args):
        out = StringIO()
        with patch(f"{MODULE}.iter_downloadable_certificates") as iter_mock:
            iter_mock.side_effect = lambda org: iter([(1, f"course-v1:{org}+A+1"), (2, f"course-v1:{org}+A+1")])
            call_command("backfill_certificate_ready_emails", *args, stdout=out)
        return out.getvalue()

    def _rows(self):
        return LearnerEmailLog.objects.filter(kind=CERTIFICATE_READY).count()  # pylint: disable=no-member

    def test_dry_run_writes_nothing(self):
        """Default mode only reports."""
        output = self._run("--org", "KSU", "--org", "SEU")

        self.assertEqual(self._rows(), 0)
        self.assertIn("4 certificates would be marked", output)

    def test_apply_writes_rows_and_is_repeatable(self):
        """--apply marks every certificate; a second run adds nothing."""
        self._run("--org", "KSU", "--apply")
        self._run("--org", "KSU", "--apply")

        self.assertEqual(self._rows(), 2)
        self.assertTrue(LearnerEmailLog.objects.filter(  # pylint: disable=no-member
            user_id=1, course_id="course-v1:KSU+A+1", kind=CERTIFICATE_READY).exists())

    def test_org_is_required(self):
        """Running without an org is an error, never "every tenant"."""
        with self.assertRaises(Exception):
            call_command("backfill_certificate_ready_emails")
