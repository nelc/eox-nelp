"""Test backend for the learner e-mails wrapper: every piece is a Mock/stand-in the tests configure."""
from contextlib import nullcontext

from mock import Mock


class BaseMessageType:
    """Stand-in of the platform message type: keeps what `personalize` receives."""

    def __init__(self, *args, **kwargs):
        self.options = {}
        self.context = {}
        self.language = None
        self.recipient = None

    def personalize(self, recipient, language, user_context):
        """Same contract as edx_ace MessageType.personalize."""
        self.recipient, self.language, self.context = recipient, language, user_context

        return self


send_and_confirm = Mock(return_value=True)
make_recipient = Mock()
get_site_for_domain = Mock()
get_base_context = Mock(return_value={})
get_user_language = Mock(return_value=None)
get_downloadable_certificate = Mock()
get_certificate_url = Mock(return_value="/certificates/abc")
iter_downloadable_certificates = Mock(return_value=iter(()))

list_orgs = Mock(return_value=[])
find_started_courses = Mock(return_value=[])
find_courses_ending = Mock(return_value=[])
find_running_courses = Mock(return_value=[])
iter_enrollments = Mock(return_value=iter(()))
iter_progress = Mock(return_value=iter(()))
get_progress = Mock(return_value=0.0)
is_enrolled = Mock(return_value=True)
has_certificate = Mock(return_value=False)
get_course_path = Mock(return_value="/courses/x/course/")


def emulate_tenant_request(site, user):  # pylint: disable=unused-argument
    """Test stand-in for the real context manager."""
    return nullcontext()
