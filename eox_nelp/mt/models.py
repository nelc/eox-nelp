"""
Models file for the MT (Ministry of Tourism) training stage delivery.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class MTTrainingStageDelivery(models.Model):
    """Record of a training stage result delivered to the Ministry of Tourism.

    One row per result we have tried to deliver. It exists so that a delivery which
    was never acknowledged can be found and retried later: the trigger is
    edge-triggered and fires once, so without this record a delivery lost at that
    instant is lost permanently and only surfaces as a support ticket.

    It is also what disambiguates the partner's response code 110, which means
    "registration not found or already has been updated". A pair we have never seen
    acknowledged is a genuine failure; a pair already acknowledged is a benign
    duplicate. The partner does not have to change anything for us to tell them apart.

    Attributes:
        national_id (str): The normalized identifier actually sent to the partner.
        course_id (str): Unique course identifier.
        stage_result (int): 1 for pass, 2 for fail.
        user (User): The account the result belongs to, for reporting. Nullable
            because the delivery is identified by what was sent, not by the account.
        attempts (int): How many times this result has been sent.
        last_response_code (str): The partner's most recent response code.
        last_response_message (str): The partner's most recent response message.
        acknowledged (bool): Whether the partner has ever accepted this result.
        acknowledged_at (datetime): When it was first accepted.
    """
    national_id = models.CharField(
        max_length=20,
        help_text="The normalized national ID that was sent to the partner.",
    )
    course_id = models.CharField(
        max_length=255,
        help_text="The course the result belongs to.",
    )
    stage_result = models.PositiveSmallIntegerField(
        help_text="Representation of pass or fail result, 1 for pass, 2 for fail.",
    )
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="mt_training_stage_deliveries",
        help_text="The account this result belongs to, for reporting only.",
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="How many times this result has been sent.",
    )
    last_response_code = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        help_text="The partner's most recent response code.",
    )
    last_response_message = models.TextField(
        blank=True,
        default="",
        help_text="The partner's most recent response message.",
    )
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the partner has ever accepted this result.",
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the partner first accepted this result.",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this result was first sent.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this result was last sent.",
    )

    class Meta:  # pylint: disable=too-few-public-methods
        """Set model constraints and the index the reconciliation query needs."""
        verbose_name = "MT Training Stage Delivery"
        verbose_name_plural = "MT Training Stage Deliveries"
        # Keyed on what was SENT, not on the account. A learner whose national_id is
        # corrected is a different identity to the partner, so the corrected value must
        # be delivered again rather than being masked by the old value's acknowledgement.
        unique_together = [["national_id", "course_id", "stage_result"]]
        indexes = [
            models.Index(fields=["acknowledged", "updated_at"], name="mt_delivery_ack_updated_idx"),
        ]

    def __str__(self):
        return (
            f"MT delivery national_id={self.national_id} course_id={self.course_id} "
            f"stage_result={self.stage_result} acknowledged={self.acknowledged}"
        )
