"""Test backend for the enrollment API wrapper: every piece is a Mock the tests configure."""
from contextlib import nullcontext

from mock import Mock

enroll_email = Mock()
send_mail_to_student = Mock()
get_email_params = Mock(return_value={})
get_course_overview = Mock()
is_actively_enrolled = Mock(return_value=False)
user_on_site = Mock(return_value=True)
account_exists = Mock(return_value=False)


def emulate_http_request(site=None, user=None):  # pylint: disable=unused-argument
    """Test stand-in for the real context manager."""
    return nullcontext()
