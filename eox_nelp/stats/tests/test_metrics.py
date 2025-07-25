"""This file contains all the test for the stats metrics.py file.

Classes:
    TestGetCachedCourses: Tests cases for get_cached_courses function.
    TestGetInstructorsMetric: Tests cases for get_instructors_metric function.
    TestGetLearnersMetric: Tests cases for get_learners_metric function.
    TestGetCoursesMetrics: Tests cases for get_courses_metrics function.
    TestGetCourseMetrics: Tests cases for get_course_metrics function.
"""
import unittest

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from mock import MagicMock, Mock, patch
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.branding import get_visible_courses
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.edxapp_wrapper.student import CourseAccessRole, CourseEnrollment
from eox_nelp.stats.metrics import (
    get_cached_courses,
    get_course_metrics,
    get_courses_metrics,
    get_instructors_metric,
    get_learners_metric,
)
from eox_nelp.tests.utils import generate_list_mock_data

User = get_user_model()
GeneratedCertificate = get_generated_certificate()


class TestGetCachedCourses(unittest.TestCase):
    """Tests cases for get_cached_courses function."""

    def tearDown(self):
        """Clean cache after every test since the method uses a decorator that caches every result."""
        cache.clear()

    def test_get_visible_courses_call(self):
        """Test that the method get_visible_courses is called once in the
        get_cached_courses execution.

        Expected behavior:
            - Result contains expected value.
            - Test function was not called again.
        """
        tenant = "http://test.com"
        get_visible_courses.return_value = {"test": True}

        get_cached_courses(tenant)

        get_visible_courses.assert_called_once_with()


class TestGetInstructorsMetric(unittest.TestCase):
    """Tests cases for get_instructors_metric function."""

    def tearDown(self):
        """Clean cache and restarts CourseAccessRole mock."""
        CourseAccessRole.reset_mock()
        cache.clear()

    def test_get_instructors_metric(self):
        """Test that the function is getting the information through the CourseAccessRole model.

        Expected behavior:
            - The get_current_site_orgs method was called once.
            - Result is the expected value.
            - The filter method was called with the right parameters.
            - The values method was called with the right parameters.
            - The distinct method was called once.
            - The count method was called once.
        """
        tenant = "http://test.com"
        filter_result = CourseAccessRole.objects.filter.return_value
        values_result = filter_result.values.return_value
        distinct_result = values_result.distinct.return_value
        distinct_result.count.return_value = 5
        configuration_helpers.get_current_site_orgs.return_value = ["org1", "org2", "org3"]

        instructors = get_instructors_metric(tenant)

        self.assertEqual(5, instructors)
        configuration_helpers.get_current_site_orgs.assert_called_once_with()
        CourseAccessRole.objects.filter.assert_called_once_with(org__in=["org1", "org2", "org3"])
        filter_result.values.assert_called_once_with("user")
        values_result.distinct.assert_called_once_with()
        distinct_result.count.assert_called_once_with()


class TestGetLearnersMetric(unittest.TestCase):
    """Tests cases for get_learners_metric function."""

    def tearDown(self):
        """Clean cache and restarts CourseEnrollment mock"""
        CourseEnrollment.reset_mock()
        cache.clear()

    @patch("eox_nelp.stats.metrics.get_current_request")
    @patch("eox_nelp.stats.metrics.get_cached_courses")
    def test_get_learners_metric(self, get_cached_courses_mock, get_current_request_mock):
        """Test that the function is getting the information through the CourseEnrollment model.

        Expected behavior:
            - The get_current_site_orgs method was called once.
            - Result is the expected value
            - The filter method was called with the right parameters.
            - The values method was called with the right parameters.
            - The distinct method was called once.
            - The count method was called once.
        """
        tenant = "http://test.com"
        get_current_request_mock.return_value.site = tenant
        filter_result = CourseEnrollment.objects.filter.return_value
        exclude_result = filter_result.exclude.return_value
        values_result = exclude_result.values.return_value
        distinct_result = values_result.distinct.return_value
        distinct_result.count.return_value = 5874
        get_cached_courses_mock.return_value = ["course1", "course2", "course3"]

        learners = get_learners_metric(tenant)

        self.assertEqual(5874, learners)
        CourseEnrollment.objects.filter.assert_called_once_with(
            course__in=["course1", "course2", "course3"],
            user__is_staff=False,
            user__is_superuser=False,
        )
        exclude_result.values.assert_called_once_with("user")
        values_result.distinct.assert_called_once_with()
        distinct_result.count.assert_called_once_with()
        get_cached_courses_mock.assert_called_once_with(tenant)


class TestGetCoursesMetrics(unittest.TestCase):
    """Tests cases for get_courses_metrics function."""

    def tearDown(self):
        """Clean cache after every test since the method uses a decorator that caches every result."""
        cache.clear()

    @patch("eox_nelp.stats.metrics.get_cached_courses")
    @patch("eox_nelp.stats.metrics.get_course_metrics")
    def test_get_courses_metrics(self, get_course_metrics_mock, get_cached_courses_mock):
        """The method get_courses_metrics just calls get_course_metrics multiple times, based on
        the available courses, So this test just verifies that the method get_course_metrics is called
        for every result of get_cached_courses.

        Expected behavior:
            - total_course returns the expected value.
            - metrics has the same length as the returned courses,
            - get_cached_courses was called once.
            - get_course_metrics_mock was called multiple times.
            - the time that get_course_metrics_mock was called is the same number of courses.
        """
        tenant = "http://test.com"
        courses = MagicMock()
        courses.__iter__.return_value = iter([
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        ])
        courses.count.return_value = 4
        get_cached_courses_mock.return_value = courses
        get_course_metrics_mock.return_value = {
            "name": "test-course"
        }

        metrics = get_courses_metrics(tenant)

        self.assertEqual(4, metrics["total_courses"])
        self.assertEqual(4, len(metrics["metrics"]))
        get_cached_courses_mock.assert_called_once_with(tenant)
        get_course_metrics_mock.assert_called()
        self.assertEqual(4, get_course_metrics_mock.call_count)


class TestGetCourseMetrics(unittest.TestCase):
    """Tests cases for get_courses_metrics function."""

    def setUp(self):
        """
        Set base variables and objects across metrics test cases.
        """
        self.course_key = CourseKey.from_string("course-v1:test+Cx105+2022_T4")
        # Prepare verticals
        self.verticals = generate_list_mock_data([
            {
                "children": [
                    {
                        "block_type": "problem",
                    },
                    {
                        "block_type": "html",
                    },
                    {
                        "block_type": "html",
                    },
                ]
            },
            {
                "children": [
                    {
                        "block_type": "problem",
                    },
                    {
                        "block_type": "video",
                    },
                    {
                        "block_type": "html",
                    },
                ]
            },
            {
                "children": [
                    {
                        "block_type": "problem",
                    },
                    {
                        "block_type": "video",
                    },
                    {
                        "block_type": "html",
                    },
                ]
            },
        ])
        # Prepare sequentials
        sequential = Mock()
        sequential.get_children.return_value = self.verticals
        self.sequentials = [
            sequential,
            sequential,
            sequential,
        ]
        # Prepare chapters
        chapter = Mock()
        chapter.get_children.return_value = self.sequentials
        self.chapters = [
            chapter,
            chapter,
            chapter,
            chapter,
        ]
        # Prepare course
        course = Mock()
        course.display_name = "testing"
        course.get_children.return_value = self.chapters
        # Set course
        modulestore.return_value.get_course.return_value = course
        self.expected_returned_enrollments = 5874
        self.expected_returned_roles = 5

        # this block set the CourseEnrollment mock and its returned values.
        filter_result = CourseEnrollment.objects.filter.return_value
        values_result = filter_result.values.return_value
        distinct_result = values_result.distinct.return_value
        distinct_result.count.return_value = self.expected_returned_enrollments

        # this block set the CourseAccessRole mock and its returned values.
        filter_result = CourseAccessRole.objects.filter.return_value
        values_result = filter_result.values.return_value
        distinct_result = values_result.distinct.return_value
        distinct_result.count.return_value = self.expected_returned_roles

        # this block use the GeneratedCertificates django test model defined
        user, _ = User.objects.get_or_create(username="vader")
        user2, _ = User.objects.get_or_create(username="vader2")
        GeneratedCertificate.objects.get_or_create(**{
            'user': user,
            'course_id': CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            'grade': '71.0',
            'status': 'downloadable',
            'mode': 'no-id-professional',

        })
        GeneratedCertificate.objects.get_or_create(**{
            'user': user2,
            'course_id': CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            'grade': '59.0',
            'status': 'notpassing',
            'mode': 'honor',

        })
        GeneratedCertificate.objects.get_or_create(**{
            'user': user,
            'course_id': CourseKey.from_string("course-v1:test2+Cx105+2022_T4"),
            'grade': '90.0',
            'status': 'downloadable',
            'mode': 'honor',
        })

    def tearDown(self):
        """Clean cache and restarts mocks"""
        # This line just verifies that de get_course modulestore method cwas called with the right parameter
        modulestore.return_value.get_course.assert_called_once_with(self.course_key)

        CourseAccessRole.reset_mock()
        CourseEnrollment.reset_mock()
        modulestore.reset_mock()
        cache.clear()

    def test_get_right_id(self):
        """Based on the initial conditions, this check that the course metrics has the expected id.

        Expected behavior:
            - 'id' value is the expected.
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(str(self.course_key), course["id"])

    def test_get_right_name(self):
        """Setting a different course display name, this verifies that the course metrics has the same name.

        Expected behavior:
            - 'name' value is the expected
        """
        modulestore.return_value.get_course.return_value.display_name = "Amazing course"

        course = get_course_metrics(self.course_key)

        self.assertEqual("Amazing course", course["name"])

    def test_get_right_learners_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected learners value.

        Expected behavior:
            - 'learners' value is the expected
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(self.expected_returned_enrollments, course["learners"])

    def test_get_right_instructors_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected instructors value.

        Expected behavior:
            - 'instructors' value is the expected
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(self.expected_returned_roles, course["instructors"])

    def test_get_right_sections_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected sections value.

        Expected behavior:
            - 'sections' value is the expected
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(len(self.chapters), course["sections"])

    def test_get_right_sub_sections_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected sub_sections value.

        Expected behavior:
            - 'sub_sections' value is the expected
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(len(self.chapters) * len(self.sequentials), course["sub_sections"])

    def test_get_right_units_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected units value.

        Expected behavior:
            - 'units' value is the expected
        """
        course = get_course_metrics(self.course_key)

        self.assertEqual(len(self.chapters) * len(self.sequentials) * len(self.verticals), course["units"])

    def test_set_empty_allowed_components(self):
        """Based on the initial conditions, this check that the course metrics has the expected components value.

        Expected behavior:
            - Components is an empty list
        """
        course = get_course_metrics(self.course_key)

        self.assertFalse(course["components"])

    def test_right_certificates_metric(self):
        """Based on the initial conditions, this check that the course metrics has the expected certificates value.

        Expected behavior:
            - Certificates dict is the expected.
        """
        cert_dict = {
            "verified": {
                "downloadable": 0,
                "notpassing": 0
            },
            "honor": {
                "downloadable": 0,
                "notpassing": 1,
            },
            "audit": {
                "downloadable": 0,
                "notpassing": 0
            },
            "professional": {
                "downloadable": 0,
                "notpassing": 0
            },
            "no-id-professional": {
                "downloadable": 1,
                "notpassing": 0
            },
            "masters": {
                "downloadable": 0,
                "notpassing": 0
            },
            "executive-education": {
                "downloadable": 0,
                "notpassing": 0
            },
            "paid-executive-education": {
                "downloadable": 0,
                "notpassing": 0
            },
            "paid-bootcamp": {
                "downloadable": 0,
                "notpassing": 0
            },
            "total": {
                "downloadable": 1,
                "notpassing": 1
            },
        }
        course = get_course_metrics(self.course_key)

        self.assertDictEqual(course["certificates"], cert_dict)

    @override_settings(STATS_SETTINGS={"API_XBLOCK_TYPES": ["html", "problem", "video"]})
    def test_set_allowed_components(self):
        """This modifies the STATS_SETTINGS value in order to test that
        the components returns the expect type of components.

        Expected behavior:
            - 'html' value is the expected
            - 'problem' value is the expected
            - 'video' value is the expected
        """
        expected_components = {}

        for vertical in self.verticals:
            for child in vertical.children:
                expected_components[child.block_type] = expected_components.get(child.block_type, 0) + 1

        expected_components = {
            k: (v * len(self.chapters) * len(self.sequentials)) for k, v in expected_components.items()
        }

        course = get_course_metrics(self.course_key)

        self.assertEqual(expected_components, course["components"])
