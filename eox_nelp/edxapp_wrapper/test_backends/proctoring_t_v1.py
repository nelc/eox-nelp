"""Test backend for eox_nelp.edxapp_wrapper.backends.proctoring_t_v1."""
from mock import Mock


def get_proctored_exam_student_attempt():
    """Return a Mock model."""
    return Mock()


def get_proctored_exam_student_attempt_status():
    """Return a Mock status class."""
    return Mock()


def get_current_exam_attempt():
    """Return a Mock function."""
    return Mock()


def get_has_access():
    """Return a Mock function."""
    return Mock()


def get_handler_authenticators():
    """Return no authenticators."""
    return ()
