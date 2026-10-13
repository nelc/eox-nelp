"""Backend with the edx-platform pieces used by the enrollment API override (Teak).

Sources (edx-platform, open-release/teak):
  lms/djangoapps/instructor/enrollment.py: enroll_email, send_mail_to_student, get_email_params
  openedx/core/lib/celery/task_utils.py: emulate_http_request
"""
# pylint: disable=import-error
from common.djangoapps.student.models import CourseEnrollment, UserAttribute, UserSignupSource
from django.contrib.auth import get_user_model
from lms.djangoapps.instructor.enrollment import enroll_email, get_email_params, send_mail_to_student  # noqa: F401
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.celery.task_utils import emulate_http_request  # noqa: F401
from rest_framework.exceptions import NotFound


def get_course_overview(course_key):
    """Return the CourseOverview of the course (key or string), or raise NotFound."""
    course_key = CourseKey.from_string(course_key) if isinstance(course_key, str) else course_key
    try:
        return CourseOverview.get_from_id(course_key)
    except CourseOverview.DoesNotExist as err:
        raise NotFound("Course not found") from err


def is_actively_enrolled(user, course_key):
    """True when the user has an active enrollment in the course."""
    return CourseEnrollment.objects.filter(user=user, course_id=course_key, is_active=True).exists()


def user_on_site(user, domain):
    """True when the user was created on, or signed up through, the site domain.

    Same two signals eox-core uses for its site-filtered account lookup.
    """
    return bool(domain) and (
        UserAttribute.get_user_attribute(user, "created_on_site") == domain
        or UserSignupSource.objects.filter(user=user, site=domain).exists()
    )


def account_exists(email):
    """True when an account (active or not) owns the email, on any tenant."""
    return get_user_model().objects.filter(email__iexact=email.strip()).exists()
