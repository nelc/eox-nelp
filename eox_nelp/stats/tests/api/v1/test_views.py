"""This file contains all the test for the stats api v1 views.py file.

Classes:
    GeneralTenantStatsViewTestCase: Tests cases for GeneralTenantStatsView.
    GeneralCourseStatsViewTestCase: Tests cases for GeneralCourseStatsView.
"""
from ddt import data, ddt
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import reverse
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.test import APITestCase


@ddt
class GeneralTenantStatsViewTestCase(APITestCase):
    """ Test GeneralTenantStatsView."""

    def setUp(self):
        """
        Create site since the view use the request.site attribute to determine the current domain.
        """
        Site.objects.get_or_create(domain="testserver")

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_default(self, mock_metrics):
        """
        Test a get request, this will verify the standard view behavior by checking the call of the metrics functions.

        Expected behavior:
            - Response data contains the expected keys.
            - Status code 200.
        """
        mock_metrics.get_learners_metric.return_value = 5
        mock_metrics.get_instructors_metric.return_value = 4875
        mock_metrics.get_courses_metrics.return_value = {
            "total_courses": 3,
            "metrics": [
                {}, {}, {}
            ],
        }
        url_endpoint = reverse("stats-api:v1:general-stats")

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(
            ["learners", "courses", "instructors", "components", "certificates"] == list(response.data.keys())
        )

    @override_settings(
        MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"],
        STATS_SETTINGS={"API_XBLOCK_TYPES": ["html", "problem", "video"]},
    )
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_total_components(self, mock_metrics):
        """
        Test that the view will calculate the total of components based on the metrics values

        Expected behavior:
            - Status code 200.
            - Components total values are the expected.
            - get_courses_metrics is called once.
        """
        total_courses = 4
        fake_metric = {
            "components": {
                "html": 5,
                "problem": 10,
                "video": 15,
            }
        }
        mock_metrics.get_learners_metric.return_value = 5
        mock_metrics.get_instructors_metric.return_value = 4875
        mock_metrics.get_courses_metrics.return_value = {
            "total_courses": total_courses,
            "metrics": [fake_metric for c in range(total_courses)],
        }
        expected_components = {key: value * total_courses for key, value in fake_metric["components"].items()}
        url_endpoint = reverse("stats-api:v1:general-stats")

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(expected_components, response.data["components"])
        mock_metrics.get_courses_metrics.assert_called_once_with("testserver")

    @override_settings(
        MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"],
    )
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_total_certificates(self, mock_metrics):
        """
        Test that the view will calculate the total of certificates based on the metrics values

        Expected behavior:
            - Status code 200.
            - Components total values are the expected.
            - get_courses_metrics is called once.
        """
        total_courses = 4
        fake_metric = {
            "certificates": {
                "verified": {"downloadable": 0, "notpassing": 0},
                "honor": {"downloadable": 0, "notpassing": 0},
                "audit": {"downloadable": 0, "notpassing": 0},
                "professional": {"downloadable": 0, "notpassing": 0},
                "no-id-professional": {"downloadable": 5, "notpassing": 4},
                "masters": {"downloadable": 10, "notpassing": 0},
                "executive-education": {"downloadable": 0, "notpassing": 1},
                "paid-executive-education": {"downloadable": 0, "notpassing": 0},
                "paid-bootcamp": {"downloadable": 0, "notpassing": 0},
                "total": {
                    "downloadable": 15,
                    "notpassing": 5,
                }
            },
        }

        mock_metrics.get_learners_metric.return_value = 5
        mock_metrics.get_instructors_metric.return_value = 4875
        mock_metrics.get_courses_metrics.return_value = {
            "total_courses": total_courses,
            "metrics": [fake_metric for c in range(total_courses)],
        }
        expected_certificates = {
            "downloadable": fake_metric["certificates"]["total"]["downloadable"] * total_courses,
            "notpassing": fake_metric["certificates"]["total"]["notpassing"] * total_courses,
        }
        url_endpoint = reverse("stats-api:v1:general-stats")

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(expected_certificates, response.data["certificates"])
        mock_metrics.get_courses_metrics.assert_called_once_with("testserver")

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @data("post", "put", "patch", "delete")
    def test_invalid_method(self, method):
        """
        This test that the view returns a method not allowed response, since the get is the unique valid method.

        Expected behavior:
            - Status code 405.
        """
        url_endpoint = reverse("stats-api:v1:general-stats")
        request = getattr(self.client, method)

        response = request(url_endpoint)

        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code)


@ddt
class GeneralCourseStatsViewTestCase(APITestCase):
    """ Test GeneralCourseStatsView."""

    def setUp(self):
        """
        Create site since the view use the request.site attribute to determine the current domain.
        """
        Site.objects.get_or_create(domain="testserver")

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_get_list(self, mock_metrics):
        """
        Test a get request, this will verify the standard view behavior by checking the call of the metrics functions.

        Expected behavior:
            - Status code 200.
            - the total_course key is present and has the expected value
            - the length of metrics is as expected.
            - get_courses_metrics is called once.
        """
        total_courses = 3
        mock_metrics.get_courses_metrics.return_value = {
            "total_courses": total_courses,
            "metrics": [{} for c in range(total_courses)],
        }
        url_endpoint = reverse("stats-api:v1:courses-stats")

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(total_courses, response.data["total_courses"])
        self.assertEqual(total_courses, len(response.data["metrics"]))
        mock_metrics.get_courses_metrics.assert_called_once_with("testserver")

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_get_detail(self, mock_metrics):
        """
        Test that a single course stats is returned.

        Expected behavior:
            - Status code 200.
            - response data is the same as the get_course_metrics result
            - get_cached_courses is called with the right parameter.
            - filter is called with the right parameter.
            - first is called once.
            - get_course_metrics is called with the right parameter.
        """
        course_id = "course-v1:potato+CS102+2023"
        courses_mock = Mock()
        course_mock = Mock()
        course_mock.id = CourseKey.from_string(course_id)
        courses_mock.filter.return_value.first.return_value = course_mock
        mock_metrics.get_cached_courses.return_value = courses_mock
        mock_metrics.get_course_metrics.return_value = {
            "id": course_id,
            "name": "PROCEDURAL SEDATION AND ANALGESIA COURSE",
            "learners": 0,
            "instructors": 1,
            "sections": 18,
            "sub_sections": 144,
            "units": 184,
            "components": {
                "discussion": 0,
                "drag-and-drop-v2": 0,
                "html": 133,
                "openassessment": 0,
                "problem": 49,
                "video": 0
            },
            "certificates": 12
        }
        url_endpoint = reverse("stats-api:v1:course-stats", args=[course_id])

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(mock_metrics.get_course_metrics.return_value, response.data)
        mock_metrics.get_cached_courses.assert_called_once_with("testserver")
        courses_mock.filter.assert_called_once_with(id=course_id)
        courses_mock.filter.return_value.first.assert_called_once()
        mock_metrics.get_course_metrics.assert_called_once_with(course_mock.id)

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @patch("eox_nelp.stats.api.v1.views.metrics")
    def test_get_not_found(self, mock_metrics):
        """
        Test that a single course stats is returned.

        Expected behavior:
            - Status code 200.
            - response data is the same as the get_course_metrics result
            - get_cached_courses is called with the right parameter.
            - filter is called with the right parameter.
            - first is called once.
            - get_course_metrics is not called.
        """
        course_id = "course-v1:potato+CS102+2023"
        courses_mock = Mock()
        courses_mock.filter.return_value.first.return_value = None
        mock_metrics.get_cached_courses.return_value = courses_mock
        url_endpoint = reverse("stats-api:v1:course-stats", args=[course_id])

        response = self.client.get(url_endpoint)

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
        mock_metrics.get_cached_courses.assert_called_once_with("testserver")
        courses_mock.filter.assert_called_once_with(id=course_id)
        courses_mock.filter.return_value.first.assert_called_once()
        mock_metrics.get_course_metrics.assert_not_called()

    @override_settings(MIDDLEWARE=["eox_tenant.middleware.CurrentSiteMiddleware"])
    @data("post", "put", "patch", "delete")
    def test_invalid_list_method(self, method):
        """
        This test that the view returns a method not allowed response, since the get is the unique valid method.

        Expected behavior:
            - Status code 405.
        """
        url_endpoint = reverse("stats-api:v1:courses-stats")
        request = getattr(self.client, method)

        response = request(url_endpoint)

        self.assertEqual(status.HTTP_405_METHOD_NOT_ALLOWED, response.status_code)
