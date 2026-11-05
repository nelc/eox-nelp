"""Wrapper edx-proctoring and the platform helpers the exam time limit check needs.

Attributes:
    backend: Imported module by using the plugin settings.
    ProctoredExamStudentAttempt: Wrapper for the attempt model.
    ProctoredExamStudentAttemptStatus: Wrapper for the attempt status class.
    get_current_exam_attempt: Wrapper for the api function that also times out an expired attempt.
    has_access: Wrapper for courseware has_access.
    HANDLER_AUTHENTICATORS: Authentication classes the XBlock handler view tries for a request without a session.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_PROCTORING_BACKEND)

ProctoredExamStudentAttempt = backend.get_proctored_exam_student_attempt()
ProctoredExamStudentAttemptStatus = backend.get_proctored_exam_student_attempt_status()
get_current_exam_attempt = backend.get_current_exam_attempt()
has_access = backend.get_has_access()
HANDLER_AUTHENTICATORS = backend.get_handler_authenticators()
