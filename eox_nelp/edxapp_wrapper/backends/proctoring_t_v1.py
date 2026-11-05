"""Backend for edx-proctoring and the platform helpers the exam time limit check needs."""
from edx_proctoring.api import get_current_exam_attempt as _get_current_exam_attempt  # pylint: disable=import-error
from edx_proctoring.models import ProctoredExamStudentAttempt  # pylint: disable=import-error
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus  # pylint: disable=import-error
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication  # pylint: disable=import-error
from lms.djangoapps.courseware.access import has_access as _has_access  # pylint: disable=import-error
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser  # pylint: disable=import-error


def get_proctored_exam_student_attempt():
    """Return the ProctoredExamStudentAttempt model."""
    return ProctoredExamStudentAttempt


def get_proctored_exam_student_attempt_status():
    """Return the ProctoredExamStudentAttemptStatus class."""
    return ProctoredExamStudentAttemptStatus


def get_current_exam_attempt():
    """Return the edx-proctoring api function that reads an attempt and times it out when expired."""
    return _get_current_exam_attempt


def get_has_access():
    """Return the courseware has_access function."""
    return _has_access


def get_handler_authenticators():
    """Return the authentication classes lms handle_xblock_callback tries, in the same order."""
    return (JwtAuthentication, BearerAuthenticationAllowInactiveUser)
