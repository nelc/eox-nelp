"""Backend for student django app module.
This file contains all the necessary student dependencies from
https://github.com/eduNEXT/edunext-platform/tree/ednx-release/mango.master/common/djangoapps/student
"""
from common.djangoapps.student import auth
from common.djangoapps.student import roles
from common.djangoapps.student.admin import CourseEnrollmentAdmin
from common.djangoapps.student.models import (  # pylint: disable=import-error
    AnonymousUserId,
    CourseAccessRole,
    CourseEnrollment,
    UserProfile,
    anonymous_id_for_user,
)


def get_course_enrollment_model():
    """Allow to get the CourseEnrollment Model from
    https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master/common/djangoapps/student/models.py#L1234
    Returns:
        CourseEnrollment Model.
    """
    return CourseEnrollment


def get_course_access_role_model():
    """Allow to get the CourseAccessRole Model from
    https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master/common/djangoapps/student/models.py#L2554
    Returns:
        CourseAccessRole Model.
    """
    return CourseAccessRole


def get_user_profile_model():
    """Allow to get the UserProfile Model from
    https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master/common/djangoapps/student/models.py#L478
    Returns:
        UserProfile Model.
    """
    return UserProfile


def get_student_roles():
    """Allow to get the Roles Module file  from
    https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master.nelp/common/djangoapps/student/roles.py
    Returns:
        Roles module.
    """
    return roles


def get_student_auth():
    """Allow to get the Auth Module file from
    https://github.com/eduNEXT/edunext-platform/blob/ednx-release/mango.master.nelp/common/djangoapps/student/auth.py
    Returns:
        Auth module.
    """
    return auth


def get_anonymous_id_for_user():
    """Allow to get anonymous_id_for_user function from
    https://github.com/nelc/edx-platform/blob/open-release/palm.nelp/common/djangoapps/student/models/user.py#L92

    Returns:
        anonymous_id_for_user function.
    """
    return anonymous_id_for_user


def get_anonymous_user_id_model():
    """Allow to get AnonymousUserId model from
    https://github.com/nelc/edx-platform/blob/open-release/palm.nelp/common/djangoapps/student/models/user.py#L73

    Returns:
        AnonymousUserId model.
    """
    return AnonymousUserId


def get_course_enrollment_admin():
    """Allow to get CourseEnrollmentAdmin model from
    https://github.com/nelc/edx-platform/blob/open-release/palm.nelp/common/djangoapps/student/admin.py#L285

    Returns:
        CourseEnrollmentAdmin model.
    """
    return CourseEnrollmentAdmin
