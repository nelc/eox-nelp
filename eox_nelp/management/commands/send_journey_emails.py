"""Management command that queues the timed learner e-mails: Message 3 (learning starts) and Message 5
(completion reminder, by progress and by course end date).

Run it hourly. A cron job has no tenant, so nothing here depends on one: the tenant switches are read per
course org, and each queued task binds its own tenant. It is safe to run any number of times: a learner
who already has a (user, course, kind) row in LearnerEmailLog is skipped when selecting and again when
sending, and the log row is claimed before the mail goes out.

To run it use:
`./manage lms send_journey_emails [--kind learning_starts --kind reminder_progress ...] [--dry-run]`.
`--dry-run` counts per org (tenant) and kind and queues nothing.
"""
import logging

from django.core.management import BaseCommand
from django.db import connection
from django.utils import timezone

from eox_nelp.learner_emails.journey import JourneyConfigError, iter_jobs
from eox_nelp.learner_emails.models import LEARNING_STARTS, REMINDER_END, REMINDER_PROGRESS
from eox_nelp.learner_emails.tasks import send_completion_reminder_email, send_learning_starts_email
from eox_nelp.learner_emails.tenant import tenant_domain_for_org

logger = logging.getLogger(__name__)
KINDS = (LEARNING_STARTS, REMINDER_PROGRESS, REMINDER_END)


def release_db_connection():
    """Close the DB connection before a long queueing loop; the next query opens a fresh one.

    Queueing runs at about 7 ms per learner and touches no table, so a course with tens of thousands of
    learners leaves the connection idle past the server's wait_timeout (300 s on the prod primary).
    The next org's query then dies with MySQL 4031 and the Job restarts the whole run from the top.
    Inside a transaction (the tests) the connection is kept, as `close_old_connections` does.
    """
    if not connection.in_atomic_block:
        connection.close()


def queue_email(kind, user_id, course_id):
    """Queue one learner's e-mail: one Celery task per learner, so a big course never blocks the command."""
    if kind == LEARNING_STARTS:
        send_learning_starts_email.delay(user_id, course_id)
    else:
        send_completion_reminder_email.delay(user_id, course_id, kind)


class Command(BaseCommand):
    """Class command to queue the learning-starts and completion-reminder e-mails."""
    help = "Queue the learning-starts and completion-reminder e-mails of the tenants that switched them on."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument("--kind", action="append", choices=KINDS, help="Only this kind (repeatable).")
        parser.add_argument("--dry-run", action="store_true", help="Count per org and kind; queue nothing.")

    def handle(self, *args, **options):
        """Select the learners due now for every enabled org and kind, and queue (or count) them."""
        now = timezone.now()
        total = 0

        for org, kind, selector in iter_jobs(kinds=options["kind"]):
            try:
                candidates = list(selector(org, now))  # every query of the job runs here, before the queueing
            except JourneyConfigError as error:
                logger.error("journey_email_config_error kind=%s %s", kind, error)
                continue
            count = len(candidates)
            if candidates and not options["dry_run"]:
                release_db_connection()
                for user_id, course_id in candidates:
                    queue_email(kind, user_id, course_id)
            self.stdout.write(f"{tenant_domain_for_org(org)} org={org} kind={kind}: {count}")
            total += count

        verb = "would be queued (dry run)" if options["dry_run"] else "queued"
        self.stdout.write(f"{total} e-mails {verb}.")
