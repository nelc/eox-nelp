"""Management command to pre-register national_id values for institution admins from an
authoritative list, before they are onboarded to integrations that identify them by it.

Accounts holding an institution role cannot set their own national_id (see
eox_nelp.user_profile.api.v1.helpers.check_national_id_lock), so staff do it here. The
command never overwrites an existing value and never moves an ID from another account:
both are decisions for a human, reported as `conflict` and `taken`.

To run it use:
`./manage lms preregister_national_ids --csv admins.csv --report report.csv [--apply]`.

The input CSV has a `national_id` column and a `username` or `email` column. The report
holds national IDs, so it is written to --report and never to stdout.
"""
import csv
import logging

from custom_reg_form.models import ExtraInfo
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from django.db import IntegrityError, transaction

from eox_nelp.user_profile.api.v1.helpers import holds_institution_role
from eox_nelp.utils import is_valid_national_id, normalize_national_id

logger = logging.getLogger(__name__)
User = get_user_model()

SET = "set"
ALREADY = "already"
CONFLICT = "conflict"
TAKEN = "taken"
NOT_ADMIN = "not_admin"
INVALID = "invalid"
NOT_FOUND = "not_found"
CLASSIFICATIONS = [SET, ALREADY, CONFLICT, TAKEN, NOT_ADMIN, INVALID, NOT_FOUND]


class Command(BaseCommand):
    """Class command to pre-register national_id values for institution admins."""

    help = "Pre-register national_id values for institution admins from an authoritative CSV."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument("--csv", required=True, help="Input CSV with national_id and username or email.")
        parser.add_argument("--report", required=True, help="Where to write the per-row report CSV.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the rows classified as set. Without it the command only reports.",
        )

    def handle(self, *args, **options):
        """Classify every input row and, with --apply, write the safe ones."""
        with open(options["csv"], newline="", encoding="utf-8-sig") as source:
            rows = [self.classify(row) for row in csv.DictReader(source)]

        if options["apply"]:
            for row in rows:
                if row["classification"] == SET:
                    row["classification"] = self.write(row)

        self.write_report(options["report"], rows)
        counts = {name: len([row for row in rows if row["classification"] == name]) for name in CLASSIFICATIONS}
        mode = "applied" if options["apply"] else "dry run"
        self.stdout.write(f"preregister_national_ids ({mode}): " + ", ".join(
            f"{name}={count}" for name, count in counts.items()
        ))

    def classify(self, row):
        """Return the row with its user, normalized national_id and classification."""
        identifier = (row.get("username") or row.get("email") or "").strip()
        national_id = normalize_national_id(row.get("national_id") or "")
        user = self.find_user(identifier)
        return {
            "identifier": identifier,
            "national_id": national_id,
            "user": user,
            "classification": self.classification(user, national_id),
        }

    def find_user(self, identifier):
        """Find the account by username, or by email when the identifier looks like one."""
        user = User.objects.filter(username=identifier).first() if identifier else None
        if user is None and "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        return user

    def classification(self, user, national_id):
        """Classify one row; never overwrites or moves an ID, those are for a human."""
        if user is None:
            return NOT_FOUND
        if not is_valid_national_id(national_id):
            return INVALID
        if not holds_institution_role(user):
            return NOT_ADMIN

        extra_info = ExtraInfo.objects.filter(user=user).first()  # pylint: disable=no-member
        current = normalize_national_id(extra_info.national_id) if extra_info and extra_info.national_id else ""
        if current:
            return ALREADY if current == national_id else CONFLICT

        taken = ExtraInfo.objects.filter(national_id=national_id).exclude(user=user).exists()  # pylint: disable=no-member
        return TAKEN if taken else SET

    def write(self, row):
        """Write one national_id; a unique-constraint race becomes `taken`, never a crash."""
        try:
            with transaction.atomic():
                extra_info, _ = ExtraInfo.objects.get_or_create(user=row["user"])  # pylint: disable=no-member
                extra_info.national_id = row["national_id"]
                extra_info.save(update_fields=["national_id"])
        except IntegrityError:
            logger.warning("preregister_national_ids: national_id already taken for user %s", row["user"].id)
            return TAKEN

        logger.info("preregister_national_ids: national_id set for user %s", row["user"].id)
        return SET

    def write_report(self, path, rows):
        """Write the per-row report; it holds national IDs, so it never goes to stdout."""
        with open(path, "w", newline="", encoding="utf-8") as report:
            writer = csv.writer(report)
            writer.writerow(["identifier", "user_id", "national_id", "classification"])
            for row in rows:
                writer.writerow([
                    row["identifier"],
                    row["user"].id if row["user"] else "",
                    row["national_id"],
                    row["classification"],
                ])
