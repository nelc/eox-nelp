"""Backend for course_modes app.

This file contains all the necessary dependencies from
https://github.com/nelc/edx-platform/tree/open-release/teak.nelp/common/djangoapps/course_modes
"""
from common.djangoapps.course_modes.models import CourseMode  # pylint: disable=import-error


def get_course_mode_model():
    """Allow to get CourseMode model from
    https://github.com/nelc/edx-platform/tree/open-release/teak.nelp/common/djangoapps/course_modes/models.py

    Returns:
        CourseMode model.
    """
    return CourseMode
