"""
Course experience models. This contains all the model related with the course user experience.

Models:
    LikeDislikeUnit: Store user decision(like or dislike) for specific unit.
    LikeDislikeCourse: Store user decision(like or dislike) for a course.
    ReportUnit: Store report reason about a specific unit.
    ReportCourse: Store report reason for a course.
"""
from django.contrib.auth import get_user_model
from django.db import models
from eventtracking import tracker
from opaque_keys.edx.django.models import UsageKeyField

from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview
from eox_nelp.utils import camel_to_snake

User = get_user_model()

RATING_OPTIONS = [
    (0, '0'),
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5')
]


class BaseLikeDislike(models.Model):
    """Base abstract model for like and dislike records.

    fields:
        author<Foreignkey>: Makes reference to the user record associated with the status.
        status<BooleanField>: True = Liked, False =d isliked and None = not-set
        course_id<Foreignkey>: Reference to a specific course.
    """
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    status = models.BooleanField(null=True)
    course_id = models.ForeignKey(CourseOverview, null=True, on_delete=models.SET_NULL)

    class Meta:
        """Set model abstract"""
        abstract = True


class BaseReport(models.Model):
    """Base abstract model for reporting records.

    fields:
        author<Foreignkey>: Makes reference to the user record associated with the reason.
        reason<CharField>: Store report reason as a code, e.g IC => Inappropriate content.
        course_id<Foreignkey>: Reference to a specific course.
    """
    REPORT_REASONS = [
        ("IC", "Inappropriate content"),
        ("GV", "Graphic violence"),
        ("HA", "Hateful or abusive content"),
        ("CI", "Copycat or impersonation"),
        ("OO", "Other objection"),
    ]

    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        choices=REPORT_REASONS,
        default=None
    )
    course_id = models.ForeignKey(CourseOverview, null=True, on_delete=models.SET_NULL)

    class Meta:
        """Set model abstract"""
        abstract = True


class BaseFeedback(models.Model):
    """Base abstract model for rating records.

    fields:
        author<Foreignkey>: Makes reference to the user record associated with the status.
        rating_content<IntegerField>: Base rate From 0 to 5.
        feedback<Charfield>: Feedbacl related to the object. Max 500 chars.
        course_id<Foreignkey>: Reference to a specific course.
        public<BooleanField>: Default True, if true the user accept showing the rating.
    """

    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    rating_content = models.IntegerField(blank=True, null=True, choices=RATING_OPTIONS)
    feedback = models.CharField(max_length=500, blank=True, null=True)
    public = models.BooleanField(null=True, default=False)
    course_id = models.ForeignKey(CourseOverview, null=True, on_delete=models.SET_NULL)

    class Meta:
        """Set model abstract"""
        abstract = True

    def save(self, *args, **kwargs):
        """Overrides save method in order to add extra functionalities."""
        super().save(*args, **kwargs)

        self.emit_feedback_event()

    def emit_feedback_event(self):
        """Emit event base on the instance attributes."""
        class_name = camel_to_snake(self.__class__.__name__)
        event_name = f"nelc.eox_nelp.course_experience.{class_name}"
        private_fields = {"id"}
        event_data = {
            field.name: field.value_to_string(self)
            for field in self._meta.fields  # pylint: disable=no-member
            if field.name not in private_fields
        }

        tracker.emit(event_name, event_data)


class LikeDislikeUnit(BaseLikeDislike):
    """Extends from BaseLikeDislike, this model will store an opinion about a specific unit.

    fields:
        item_id<UsageKeyField>: Unit identifier.
    """
    item_id = UsageKeyField(max_length=255)

    class Meta:
        """Set constrain for author an item id"""
        unique_together = [["author", "item_id"]]
        indexes = [
            models.Index(fields=["author", "item_id"], name="likedislike_author_item_idx"),
        ]


class LikeDislikeCourse(BaseLikeDislike):
    """Extends from BaseLikeDislike, this model will store an opinion about a specific course
    and set constrains.
    """
    class Meta:
        """Set constrain for author an course id"""
        unique_together = [["author", "course_id"]]
        indexes = [
            models.Index(fields=["author", "course_id"], name="likedislike_author_course_idx"),
        ]


class ReportUnit(BaseReport):
    """Extends from BaseReport, this model will store a report about a specific unit.

    fields:
        item_id<UsageKeyField>: Unit identifier.
    """
    item_id = UsageKeyField(max_length=255)

    class Meta:
        """Set constrain for author an item id"""
        unique_together = [["author", "item_id"]]
        indexes = [
            models.Index(fields=["author", "item_id"], name="report_author_item_idx"),
        ]


class ReportCourse(BaseReport):
    """Extends from BaseReport, this model will store a report about a specific course
    and set constrains.
    """
    class Meta:
        """Set constrain for author an course id"""
        unique_together = [["author", "course_id"]]
        indexes = [
            models.Index(fields=["author", "course_id"], name="report_author_course_idx"),
        ]


class FeedbackUnit(BaseFeedback):
    """Extends from BaseFeedback, this model will store a report about a specific unit.

    fields:
        item_id<UsageKeyField>: Unit identifier.
    """
    item_id = UsageKeyField(max_length=255)

    class Meta:
        """Set constrain for author an item id"""
        unique_together = [["author", "item_id"]]
        indexes = [
            models.Index(fields=["author", "item_id"], name="feedback_author_item_idx"),
        ]


class FeedbackCourse(BaseFeedback):
    """Extends from BaseFeedback, this model will store a report about a specific course
    and set constrains.
    fields:
        rating_instructors<IntegerField>:: Rate the staff and instructors related the course. From 0 to 5.
        recommended<boolean>: recommeded the course with true.

    """
    rating_instructors = models.IntegerField(blank=True, null=True, choices=RATING_OPTIONS)
    recommended = models.BooleanField(null=True, default=True)

    class Meta:
        """Set constrain for author an course id"""
        unique_together = [["author", "course_id"]]
        indexes = [
            models.Index(fields=["author", "course_id"], name="feedback_author_course_idx"),
        ]
