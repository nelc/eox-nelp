"""Log that makes every learner e-mail go out once."""
from django.db import models
from django.utils import timezone

# `kind` values. A new learner e-mail adds a constant here, nothing else changes in the table.
CERTIFICATE_READY = "certificate_ready"
LEARNING_STARTS = "learning_starts"
REMINDER_PROGRESS = "reminder_progress"  # Message 5, trigger (a): progress at/over the tenant threshold
REMINDER_END = "reminder_end"  # Message 5, trigger (b): the course end date is inside the window


class LearnerEmailLog(models.Model):
    """One row per learner e-mail that was claimed: (user, course, kind) is unique.

    The row is inserted BEFORE the mail is sent, so two racing workers cannot both send it,
    and it is what the backfill command writes to say "this learner already has it".

    There is deliberately NO foreign key to auth_user: adding one to a big table stalled a
    production migration for 11 minutes on 2026-10-01. Plain integers keep the migration instant.

    Attributes:
        user_id (int): Id of the learner (not a foreign key, see above).
        course_id (str): Course key string.
        kind (str): Which e-mail it is, one of the constants of this module.
        created_at (datetime): When the row was written.
    """
    user_id = models.IntegerField()
    course_id = models.CharField(max_length=255)
    kind = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:  # pylint: disable=too-few-public-methods
        """The unique constraint IS the exactly-once guarantee."""
        constraints = [
            models.UniqueConstraint(fields=["user_id", "course_id", "kind"], name="learner_email_log_once"),
        ]

    def __str__(self):
        return f"{self.kind} user_id={self.user_id} course_id={self.course_id}"
