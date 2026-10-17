"""Management command that marks existing certificates as "email already sent".

Run it BEFORE enabling `CERTIFICATE_READY_EMAIL_ENABLED` for a tenant. Otherwise the first time
any old certificate is re-saved it would be mailed as if it were new. It only writes log rows
(never sends anything) and is a dry run unless `--apply` is given.

To run it use:
`./manage lms backfill_certificate_ready_emails --org ORG [--org ORG2 ...] [--apply]`
where the orgs are the tenant's `course_org_filter`.
"""
import logging
from itertools import islice

from django.core.management import BaseCommand

from eox_nelp.edxapp_wrapper.learner_emails import iter_downloadable_certificates
from eox_nelp.learner_emails.models import CERTIFICATE_READY, LearnerEmailLog

logger = logging.getLogger(__name__)
BATCH_SIZE = 1000


class Command(BaseCommand):
    """Class command to write the "already sent" rows of the certificate-ready e-mail."""
    help = "Mark every existing downloadable certificate of the given orgs as already e-mailed."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument("--org", action="append", required=True, help="Org of the tenant (repeatable).")
        parser.add_argument("--apply", action="store_true", help="Write the rows. Without it only counts.")

    def handle(self, *args, **options):
        """Count (dry run) or write (apply) the rows; rows that already exist are left alone."""
        total = 0

        for org in options["org"]:
            pairs = iter_downloadable_certificates(org)
            count = 0
            while batch := list(islice(pairs, BATCH_SIZE)):
                count += len(batch)
                if options["apply"]:
                    LearnerEmailLog.objects.bulk_create(  # pylint: disable=no-member
                        [LearnerEmailLog(user_id=user_id, course_id=course_id, kind=CERTIFICATE_READY)
                         for user_id, course_id in batch],
                        ignore_conflicts=True,
                    )
            self.stdout.write(f"org={org}: {count} downloadable certificates")
            total += count

        mode = "marked as sent" if options["apply"] else "would be marked as sent (dry run, use --apply)"
        self.stdout.write(f"{total} certificates {mode}.")
