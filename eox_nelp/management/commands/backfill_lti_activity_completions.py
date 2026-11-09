"""Management command that completes the LTI blocks whose tool already reported the activity Completed.

It replays `complete_lti_block_from_ags_score` (the function the LtiAgsScore receiver runs) over the
AGS scores saved before that receiver existed. It is a dry run unless `--apply` is given, and
re-running it is safe: blocks that are already complete are counted and left alone.

To run it use:
`./manage.py lms backfill_lti_activity_completions --course-key COURSE [--course-key COURSE2 ...]
[--user-id ID] [--limit N] [--apply]`
"""
from collections import Counter

from django.core.management import BaseCommand

from eox_nelp.edxapp_wrapper.lti_consumer import LtiAgsScore
from eox_nelp.signals.utils import LTI_ACTIVITY_COMPLETED, complete_lti_block_from_ags_score


class Command(BaseCommand):
    """Class command to complete the LTI blocks of the AGS scores reported Completed."""
    help = "Complete the LTI blocks whose tool reported the activity Completed (dry run unless --apply)."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument("--course-key", action="append", required=True, help="Course key (repeatable).")
        parser.add_argument("--user-id", type=int, help="Only this learner (platform user id).")
        parser.add_argument("--limit", type=int, help="Stop after completing this many blocks.")
        parser.add_argument("--apply", action="store_true", help="Write the completions. Without it only counts.")

    def handle(self, *args, **options):
        """Count (dry run) or write (apply) the missing completions, per course and outcome."""
        total = Counter()

        for course_key in options["course_key"]:
            course_id = course_key.replace("course-v1:", "", 1)
            scores = LtiAgsScore.objects.filter(
                activity_progress=LTI_ACTIVITY_COMPLETED,
                score_given__isnull=True,
                line_item__resource_link_id__startswith=f"block-v1:{course_id}+",
            ).select_related("line_item__lti_configuration").order_by("id")
            outcomes = Counter()

            for score in scores.iterator():
                if options["limit"] is not None and total["completed"] + outcomes["completed"] >= options["limit"]:
                    break

                outcomes[complete_lti_block_from_ags_score(
                    score, apply=options["apply"], only_user_id=options["user_id"],
                )] += 1

            self.stdout.write(f"{course_key}: {dict(outcomes)}")
            total.update(outcomes)

        mode = "completed" if options["apply"] else "would be completed (dry run, use --apply)"
        self.stdout.write(f"{total['completed']} LTI blocks {mode}. All outcomes: {dict(total)}")
