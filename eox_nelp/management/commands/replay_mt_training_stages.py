""""Management command to find training stage results the Ministry of Tourism has
never acknowledged, and optionally re-send them.

Delivery is edge-triggered, so results lost before the delivery record existed leave
no trace at all. This command reconstructs them from the certificates the platform
issued, which is the durable evidence that a learner passed.

The default is a report. `--send` is required to put any traffic on the partner API.

To run it use:
`./manage lms replay_mt_training_stages --org MT [--course <id>] [--limit N] [--send]`.
"""
import logging

from django.core.management import BaseCommand

from eox_nelp.edxapp_wrapper.certificates import models as certificates_models
from eox_nelp.mt.models import MTTrainingStageDelivery
from eox_nelp.signals.tasks import update_mt_training_stage
from eox_nelp.utils import is_valid_national_id, normalize_national_id

logger = logging.getLogger(__name__)

STAGE_RESULT_PASS = 1


class Command(BaseCommand):
    """Report, and optionally re-send, unacknowledged MT training stage results."""
    help = "Find training stage results MT never acknowledged and optionally re-send them."

    def add_arguments(self, parser):
        """Add the command arguments."""
        parser.add_argument(
            "--org",
            required=True,
            help="Course organization to scope the replay to, e.g. MT.",
        )
        parser.add_argument(
            "--course",
            help="Restrict to a single course id.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Stop after this many results.",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="Actually re-send. Without it the command only reports.",
        )

    def handle(self, *args, **options):
        """Report the backlog and, with --send, re-send it."""
        pending = self.collect(options["org"], options["course"], options["limit"])

        self.stdout.write(f"{len(pending)} passing results have no acknowledged delivery.")

        if not options["send"]:
            for row in pending[:20]:
                self.stdout.write(f"  {row['national_id']}  {row['course_id']}")

            if len(pending) > 20:
                self.stdout.write(f"  ... and {len(pending) - 20} more")

            self.stdout.write("Dry run. Re-run with --send to deliver these.")

            return

        for row in pending:
            MTTrainingStageDelivery.objects.get_or_create(  # pylint: disable=no-member
                national_id=row["national_id"],
                course_id=row["course_id"],
                stage_result=STAGE_RESULT_PASS,
                defaults={"user_id": row["user_id"]},
            )
            update_mt_training_stage.delay(
                course_id=row["course_id"],
                national_id=row["national_id"],
                stage_result=STAGE_RESULT_PASS,
            )

        logger.error("MT replay queued %s results for org %s.", len(pending), options["org"])
        self.stdout.write(f"Queued {len(pending)} results.")

    def collect(self, org, course_id, limit):
        """Every passing learner-course pair in the org without an acknowledged delivery.

        A certificate is the durable evidence that the learner passed. Pairs whose
        national ID cannot be matched by the partner are skipped rather than sent,
        since an unmatchable delivery is guaranteed to fail.
        """
        certificates = certificates_models.GeneratedCertificate.objects.filter(
            status="downloadable",
            user__is_active=True,
        ).select_related("user")

        if course_id:
            certificates = certificates.filter(course_id=course_id)
        else:
            certificates = certificates.filter(course_id__startswith=f"course-v1:{org}+")

        acknowledged = set(
            MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
                acknowledged=True,
                stage_result=STAGE_RESULT_PASS,
            ).values_list("national_id", "course_id")
        )

        pending = []

        for certificate in certificates.iterator():
            user = certificate.user
            extra_info = getattr(user, "extrainfo", None)
            national_id = normalize_national_id(
                extra_info.national_id if extra_info and extra_info.national_id else user.username
            )

            if not is_valid_national_id(national_id):
                continue

            course = str(certificate.course_id)

            if (national_id, course) in acknowledged:
                continue

            pending.append({"national_id": national_id, "course_id": course, "user_id": user.id})

            if limit and len(pending) >= limit:
                break

        return pending
