"""This file contains all the test for the preregister_national_ids.py command.

Classes:
    PreregisterNationalIdsTestCase: Test the classification, dry run and apply modes.
"""
import csv
import os
import tempfile
from io import StringIO
from unittest.mock import patch

from custom_reg_form.models import ExtraInfo
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

User = get_user_model()
COMMAND = "eox_nelp.management.commands.preregister_national_ids"


class PreregisterNationalIdsTestCase(TestCase):
    """Test case for the preregister_national_ids command."""

    def setUp(self):
        """Create users for every classification and stub the institution role check."""
        self.admin_new = User.objects.create(username="admin-new", email="admin-new@example.com")
        self.admin_same = User.objects.create(username="admin-same")
        self.admin_other = User.objects.create(username="admin-other")
        self.learner = User.objects.create(username="learner")
        self.squatter = User.objects.create(username="admin-squatted")
        ExtraInfo.objects.create(user=self.admin_same, national_id="1000000401")  # pylint: disable=no-member
        ExtraInfo.objects.create(user=self.admin_other, national_id="1000000402")  # pylint: disable=no-member
        ExtraInfo.objects.create(user=self.learner, national_id="1000000499")  # pylint: disable=no-member
        patcher = patch(f"{COMMAND}.holds_institution_role", side_effect=lambda user: user.username.startswith("admin"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.mkdtemp()
        self.report = os.path.join(self.tmp, "report.csv")

    def run_command(self, rows, *args):
        """Write the input CSV, run the command and return (stdout, report rows)."""
        source = os.path.join(self.tmp, "admins.csv")
        with open(source, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["username", "email", "national_id"])
            writer.writeheader()
            writer.writerows(rows)
        out = StringIO()
        call_command("preregister_national_ids", "--csv", source, "--report", self.report, *args, stdout=out)
        with open(self.report, newline="", encoding="utf-8") as handle:
            report = {row["identifier"]: row for row in csv.DictReader(handle)}
        return out.getvalue(), report

    def all_rows(self):
        """One input row per classification."""
        return [
            {"email": "admin-new@example.com", "national_id": "١٠٠٠٠٠٠٤٠٣"},
            {"username": "admin-same", "national_id": "1000000401"},
            {"username": "admin-other", "national_id": "1000000404"},
            {"username": "admin-squatted", "national_id": "1000000499"},
            {"username": "learner", "national_id": "1000000405"},
            {"username": "admin-new", "national_id": "12345"},
            {"username": "nobody", "national_id": "1000000406"},
        ]

    def test_dry_run_classifies_and_writes_nothing(self):
        """
        Test every classification in dry-run mode.

        Expected behavior:
            - Each row gets its classification in the report.
            - Arabic-Indic digits are normalized.
            - Nothing is written.
            - Stdout carries counts, never a national ID.
        """
        out, report = self.run_command(self.all_rows())

        self.assertEqual(report["admin-new@example.com"]["classification"], "set")
        self.assertEqual(report["admin-new@example.com"]["national_id"], "1000000403")
        self.assertEqual(report["admin-same"]["classification"], "already")
        self.assertEqual(report["admin-other"]["classification"], "conflict")
        self.assertEqual(report["admin-squatted"]["classification"], "taken")
        self.assertEqual(report["learner"]["classification"], "not_admin")
        self.assertEqual(report["admin-new"]["classification"], "invalid")
        self.assertEqual(report["nobody"]["classification"], "not_found")
        self.assertFalse(ExtraInfo.objects.filter(user=self.admin_new).exists())  # pylint: disable=no-member
        self.assertIn("dry run", out)
        self.assertNotIn("100000040", out)

    def test_apply_writes_only_set_rows(self):
        """
        Test that --apply writes the set rows and never overwrites or moves an ID.

        Expected behavior:
            - The new admin gets the national_id.
            - The conflicting admin keeps their own national_id.
            - The squatted ID stays where it is.
        """
        _, report = self.run_command(self.all_rows(), "--apply")

        self.assertEqual(report["admin-new@example.com"]["classification"], "set")
        self.assertEqual(self.admin_new.extrainfo.national_id, "1000000403")
        self.admin_other.extrainfo.refresh_from_db()
        self.assertEqual(self.admin_other.extrainfo.national_id, "1000000402")
        self.assertEqual(
            ExtraInfo.objects.get(national_id="1000000499").user,  # pylint: disable=no-member
            self.learner,
        )

    def test_apply_race_becomes_taken(self):
        """
        Test that a unique-constraint race at write time is reported as taken.

        Expected behavior:
            - The row is classified as taken instead of raising.
        """
        with patch.object(ExtraInfo, "save", side_effect=IntegrityError("duplicate")):
            _, report = self.run_command(
                [{"username": "admin-new", "national_id": "1000000407"}],
                "--apply",
            )

        self.assertEqual(report["admin-new"]["classification"], "taken")
