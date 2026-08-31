""""Management command to re-send training stage results the Ministry of Tourism has
never acknowledged.

Delivery is edge-triggered: COURSE_GRADE_NOW_PASSED fires once per learner per course
and never fires again, so a result lost at that instant is lost permanently unless
something goes looking for it. This is that something, run on a schedule.

Each result is handed to `update_mt_training_stage`, which applies the retry window
itself, so nothing is sent before it is due.

To run it use:
`./manage lms reconcile_mt_training_stages [--limit N]`.
"""
import logging

from django.core.management import BaseCommand

from eox_nelp.signals.tasks import reconcile_mt_training_stages

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Class command to re-send unacknowledged MT training stage results."""
    help = "Re-send training stage results the Ministry of Tourism never acknowledged."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of results to re-send in this run.",
        )

    def handle(self, *args, **options):
        """Run one reconciliation pass synchronously."""
        result = reconcile_mt_training_stages(limit=options["limit"])

        self.stdout.write(
            f"Re-sent {result['resent']} results. "
            f"{result['unacknowledged']} remain unacknowledged."
        )
