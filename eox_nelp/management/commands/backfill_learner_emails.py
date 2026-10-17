"""Management command that marks the learners who are due an e-mail right now as "already sent".

Run it BEFORE switching a tenant's e-mail on, so that turning it on mails only what happens afterwards,
not whoever the selection would pick up at that very moment. It uses exactly the selection the sending
command uses (so "eligible" means the same thing), only ignores the tenant switch, and writes log rows
without sending anything. A dry run unless `--apply` is given.

To run it use:
`./manage lms backfill_learner_emails --org ORG [--org ORG2 ...] [--kind learning_starts ...] [--apply]`
(`certificate_ready` has its own `backfill_certificate_ready_emails`).
"""
from itertools import islice

from django.core.management import BaseCommand
from django.utils import timezone

from eox_nelp.learner_emails.journey import JourneyConfigError, iter_jobs
from eox_nelp.learner_emails.models import LEARNING_STARTS, REMINDER_END, REMINDER_PROGRESS, LearnerEmailLog
from eox_nelp.learner_emails.tenant import tenant_domain_for_org

BATCH_SIZE = 1000
KINDS = (LEARNING_STARTS, REMINDER_PROGRESS, REMINDER_END)


class Command(BaseCommand):
    """Class command to write the "already sent" rows of the timed learner e-mails."""
    help = "Mark the learners currently due a timed e-mail as already e-mailed (before enabling a tenant)."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument("--org", action="append", required=True, help="Org of the tenant (repeatable).")
        parser.add_argument("--kind", action="append", choices=KINDS, help="Only this kind (repeatable).")
        parser.add_argument("--apply", action="store_true", help="Write the rows. Without it only counts.")

    def handle(self, *args, **options):
        """Count (dry run) or write (apply) the rows; rows that already exist are left alone."""
        now = timezone.now()
        total = 0

        for org, kind, selector in iter_jobs(kinds=options["kind"], orgs=options["org"], ignore_switch=True):
            count = 0
            try:
                pairs = selector(org, now)
                while batch := list(islice(pairs, BATCH_SIZE)):
                    count += len(batch)
                    if options["apply"]:
                        LearnerEmailLog.objects.bulk_create(  # pylint: disable=no-member
                            [LearnerEmailLog(user_id=user_id, course_id=course_id, kind=kind)
                             for user_id, course_id in batch],
                            ignore_conflicts=True,
                        )
            except JourneyConfigError as error:
                self.stderr.write(f"skipped kind={kind}: {error}")
                continue
            self.stdout.write(f"{tenant_domain_for_org(org)} org={org} kind={kind}: {count}")
            total += count

        mode = "marked as sent" if options["apply"] else "would be marked as sent (dry run, use --apply)"
        self.stdout.write(f"{total} learners {mode}.")
