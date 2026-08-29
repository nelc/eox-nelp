"""Backend for the pre-enrollment (white listings) functionality of eox-core.

This only overrides `create_pre_enrollment` from
https://github.com/eduNEXT/eox-core/blob/open-release/teak.nelp/eox_core/edxapp_wrapper/backends/pre_enrollment_l_v1.py
so the duplicate key error of an already existing pre-enrollment does not break the surrounding
atomic block. Without the savepoint the IntegrityError leaves the transaction unusable, the
intended NotFound is replaced by a TransactionManagementError and the caller receives a 500
instead of a 404.

Set it with EOX_CORE_PRE_ENROLLMENT_BACKEND = "eox_nelp.edxapp_wrapper.backends.pre_enrollment_n_v1"
"""
# pylint: disable=import-error
import logging

from common.djangoapps.student.models import CourseEnrollmentAllowed
from django.db import IntegrityError, transaction
from eox_core.edxapp_wrapper.backends.pre_enrollment_l_v1 import (  # pylint: disable=unused-import
    delete_pre_enrollment,
    get_pre_enrollment,
    update_pre_enrollment,
)
from eox_core.edxapp_wrapper.coursekey import get_valid_course_key
from eox_core.edxapp_wrapper.courseware import get_courseware_courses
from rest_framework.exceptions import NotFound

LOG = logging.getLogger(__name__)


def create_pre_enrollment(*args, **kwargs):
    """
    Create pre-enrollment of given user in the course provided.

    Example:
        >>>create_pre_enrollment(
            {
            "email": "bob@example.com",
            "course_id": course-v1-edX-DemoX-1T2015",
            "auto_enroll": "False"
            }
        )
    """
    warnings = []
    email = kwargs.get('email')
    auto_enroll = kwargs.get('auto_enroll', False)
    course_id = kwargs.pop('course_id')

    try:
        course_key = get_valid_course_key(course_id)

        with transaction.atomic():
            pre_enrollment = CourseEnrollmentAllowed.objects.create(course_id=course_key, **kwargs)

        # Check if the course exists otherwise add a warning
        course = get_courseware_courses().get_course(course_key)
        LOG.info('Creating regular pre-enrollment for email: %s course_id: %s auto_enroll: %s', email, course.id, auto_enroll)
    except IntegrityError:
        pre_enrollment = None
        raise NotFound(f'Pre-enrollment already exists for email: {email} course_id: {course_id}') from IntegrityError
    except ValueError:
        warnings = [f'Course with course_id:{course_id} does not exist']
    return pre_enrollment, warnings
