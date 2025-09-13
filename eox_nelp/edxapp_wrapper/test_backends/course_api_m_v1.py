"""Backend test abstraction."""
from edx_rest_framework_extensions.paginators import NamespacedPageNumberPagination

from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview
from eox_nelp.edxapp_wrapper.test_backends import DummyListView, DummyRetrieveView, DummySerializer


def get_course_detail_serializer():
    """Return test class.
    Returns:
        Mock class.
    """
    return TestCourseSerializer


def get_course_detail_view():
    """Return test class.
    Returns:
        Mock class.
    """
    return TestCourseDetailView


def get_course_list_view():
    """Return test class.
    Returns:
        Mock class.
    """
    return TestCourseListView


class TestCourseListView(DummyListView):
    pagination_class = NamespacedPageNumberPagination
    def get_queryset(self):
        return CourseOverview.objects.all()

class TestCourseDetailView(DummyRetrieveView):
    queryset = CourseOverview.objects.all()
    lookup_url_kwarg = "course_key_string"


class TestCourseSerializer(DummySerializer):
    def get_overview(*args):
        return TEST_RAW_OVERVIEW  # Mock mongo raw_overview for tests


TEST_RAW_OVERVIEW = """
<section class=\"about\">\n  <h2>About This Course</h2>\n
<p>The long course description should contain 150-400 words.</p>\n\n
<p>This is paragraph 2 of the long course description. Add more paragraphs as needed.</p>\n</section>\n
\n<section class=\"prerequisites\">\n
<h2>Requirements</h2>\n
<p>Add information about the skills and knowledge students need to take this course.</p>\n
</section>\n\n<section class=\"course-staff\">\n  <h2>Course Staff</h2>\n
 <article class=\"teacher\">\n
<div class=\"teacher-image\">\n
<img src=\"/static/images/placeholder-faculty.png\" align=\"left\"
style=\"margin:0 20 px 0\" alt=\"Course Staff Image #1\">\n    </div>\n\n
<h3>Staff Member #1</h3>\n    <p>Biography of instructor/staff member #1</p>\n
</article>\n\n  <article class=\"teacher\">\n    <div class=\"teacher-image\">\n
<img src=\"/static/images/placeholder-faculty.png\" align=\"left\" style=\"margin:0 20 px 0\"
alt=\"Course Staff Image #2\">\n    </div>\n\n    <h3>Staff Member #2</h3>\n
<p>Biography of instructor/staff member #2</p>\n  </article>\n</section>\n
\n<section class=\"faq\">\n
<section class=\"responses\">\n    <h2>Frequently Asked Questions</h2>\n    <article class=\"response\">\n
<h3>What web browser should I use?</h3>\n
<p>The Open edX platform works best with current versions of: </p>
<p>Chrome, Edge, Firefox, Internet Explorer, or Safari.</p>\n
<p>See our <a href=
\"https://edx.readthedocs.org/projects/open-edx-learner-guide/en/latest/front_matter/browsers.html\">
list of supported browsers</a> for the most up-to-date information.</p>\n
</article>\n\n    <article class=\"response\">\n      <h3>Question #2</h3>\n
<p>Your answer would be displayed here.</p>\n
 </article>\n  </section>\n</section>\n
"""
