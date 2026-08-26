"""Test backend for course modes module."""
from django.db import models

from eox_nelp.edxapp_wrapper.test_backends import create_test_model


def get_course_mode_model():
    """Return test model.

    Returns:
        CourseMode dummy model.
    """
    course_mode_fields = {
        # ForeignKey to the test CourseOverview model created in the same test app
        "course": models.ForeignKey(
            "eox_nelp.CourseOverview",
            db_constraint=False,
            db_index=True,
            related_name="modes",
            on_delete=models.DO_NOTHING,
        ),
        "mode_slug": models.CharField(max_length=100),
        "mode_display_name": models.CharField(max_length=255),
        "min_price": models.IntegerField(default=0),
        "currency": models.CharField(default="usd", max_length=8),
        "__str__": lambda self: f"{self.course_id} : {self.mode_slug}, min={self.min_price}",
    }

    return create_test_model(
        "CourseMode", "eox_nelp", __package__, course_mode_fields
    )
