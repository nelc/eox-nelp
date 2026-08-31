"""Management command to normalize national_id values that were stored in a form
no downstream service can match, most commonly Arabic-Indic digits.

The command never resolves a collision. `ExtraInfo.national_id` is unique, so two
rows normalizing to the same value are two accounts claiming one identity, and
which of them survives is a decision for a human.

To run it use:
`./manage lms backfill_national_ids [--site mt.futurex.sa] [--limit N] [--apply]`.
"""
import csv
import logging
import sys

from custom_reg_form.models import ExtraInfo
from django.core.management import BaseCommand
from django.db import IntegrityError
from eox_core.edxapp_wrapper.users import get_user_signup_source

from eox_nelp.utils import is_valid_national_id, normalize_national_id

logger = logging.getLogger(__name__)

NORMALIZABLE = "normalizable"
COLLISION = "collision"
UNRECOVERABLE = "unrecoverable"


class Command(BaseCommand):
    """Class command to audit and normalize malformed national_id values."""
    help = "Audit and normalize national_id values that downstream services cannot match."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument(
            "--site",
            help="Only consider users whose UserSignupSource matches this site, e.g. mt.futurex.sa.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Stop after examining this many malformed rows.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the normalizable rows. Without it the command only reports.",
        )

    def handle(self, *args, **options):
        """Classify every malformed national_id and, with --apply, write the safe ones."""
        rows = self.classify(self.get_queryset(options["site"]), options["limit"])
        self.write_report(rows)

        counts = {
            classification: len([row for row in rows if row["classification"] == classification])
            for classification in (NORMALIZABLE, COLLISION, UNRECOVERABLE)
        }
        logger.info("national_id audit: %s", counts)

        if not options["apply"]:
            self.stdout.write(
                f"Dry run. {counts[NORMALIZABLE]} normalizable, {counts[COLLISION]} collision, "
                f"{counts[UNRECOVERABLE]} unrecoverable. Re-run with --apply to write."
            )
            return

        written = self.apply(rows)
        self.stdout.write(
            f"Wrote {written} of {counts[NORMALIZABLE]} normalizable rows. "
            f"{counts[COLLISION]} collisions need a human decision."
        )

    def get_queryset(self, site):
        """Return the ExtraInfo rows that carry a national_id, optionally scoped to one site."""
        queryset = ExtraInfo.objects.exclude(  # pylint: disable=no-member
            national_id__isnull=True,
        ).exclude(
            national_id="",
        ).select_related("user").order_by("id")

        if site:
            signup_source = get_user_signup_source()
            queryset = queryset.filter(
                user__in=signup_source.objects.filter(site=site).values("user"),
            )

        return queryset

    def classify(self, queryset, limit):
        """Classify every row whose national_id is not already valid.

        A row is normalizable when normalizing it produces a valid national_id that no
        other row holds, a collision when another row already holds that value, and
        unrecoverable when normalizing does not produce a valid national_id at all.
        """
        rows = []

        for extra_info in queryset.iterator():
            stored = extra_info.national_id

            if is_valid_national_id(stored):
                continue

            normalized = normalize_national_id(stored)

            if not is_valid_national_id(normalized):
                classification = UNRECOVERABLE
                holder = None
            else:
                holder = ExtraInfo.objects.filter(  # pylint: disable=no-member
                    national_id=normalized,
                ).exclude(pk=extra_info.pk).first()
                classification = COLLISION if holder else NORMALIZABLE

            rows.append({
                "extra_info_id": extra_info.pk,
                "user_id": extra_info.user_id,
                "username": extra_info.user.username,
                "stored": stored,
                "normalized": normalized,
                "classification": classification,
                "held_by_user_id": holder.user_id if holder else "",
            })

            if limit and len(rows) >= limit:
                break

        return rows

    def write_report(self, rows):
        """Write every classified row to stdout as CSV."""
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=[
                "extra_info_id",
                "user_id",
                "username",
                "stored",
                "normalized",
                "classification",
                "held_by_user_id",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    def apply(self, rows):
        """Write the normalizable rows, leaving every other classification untouched."""
        written = 0

        for row in rows:
            if row["classification"] != NORMALIZABLE:
                continue

            try:
                ExtraInfo.objects.filter(  # pylint: disable=no-member
                    pk=row["extra_info_id"],
                ).update(national_id=row["normalized"])
            except IntegrityError:
                # Another row claimed the value between classification and now, which makes
                # this a collision after all. Report it and leave both rows alone.
                row["classification"] = COLLISION
                logger.warning(
                    "national_id collision on write for user %s: %s -> %s",
                    row["user_id"], row["stored"], row["normalized"],
                )
                continue

            logger.info(
                "national_id normalized for user %s: %s -> %s",
                row["user_id"], row["stored"], row["normalized"],
            )
            written += 1

        return written
