"""
Unit tests for Certificates API v1 views.
"""
from custom_reg_form.models import ExtraInfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.edxapp_wrapper.certificates import utils as certificates_utils
from eox_nelp.edxapp_wrapper.course_overviews import get_course_overviews
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers

User = get_user_model()
GeneratedCertificate = get_generated_certificate()


class UserCertificateListViewTests(APITestCase):
    """
    Test suite for the UserCertificateListView API view.
    """

    def setUp(self):
        """
        Set up the test data and mock clients for the test suite.
        """
        self.national_id = "1234567890"
        self.url = reverse("certificates-api:v1:user-certificate-list", args=[self.national_id])
        self.student, _ = User.objects.get_or_create(
            username="student",
            email="student@example.com",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=self.student,
            arabic_name="مسؤل",
            national_id=self.national_id,
            occupation="student",
        )
        GeneratedCertificate.objects.create(**{
            'user': self.student,
            'course_id': CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            'grade': '71.0',
            'status': 'downloadable',
            'mode': 'honor',
            "verify_uuid": "2c97649425bb49189470f05bf7d98c1a",

        })
        self.staff_user = User.objects.create_user(
            username="staff_user",
            email="staff@example.com",
            password="testpassword",
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular_user",
            email="regular@example.com",
            password="testpassword",
            is_staff=False
        )

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificates_success(self):
        """
        Test successful retrieval of user certificates.

        Expected behavior:
            - Status code 200.
            - Return expected username.
            - Return expected national ID.
            - Return expected serialized certificates.
        """
        self.client.force_authenticate(user=self.staff_user)
        expected_certificates_data = {
            "tenant": "test.openedx.io",
            "org": "test",
            "course_id": "course-v1:test+Cx105+2022_T4",
            "course_name": "TestingCourse",
            "status": "downloadable",
            "mode": "honor",
            "certificate_url": "http://test.openedx.io/certificates/2c97649425bb49189470f05bf7d98c1a"
        }
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]
        certificates_utils.get_certificate_url.return_value = "/certificates/2c97649425bb49189470f05bf7d98c1a"
        get_course_overviews.return_value = [{"display_name": "TestingCourse"}]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student")
        self.assertEqual(response.data["national_id"], self.national_id)
        self.assertEqual(response.data["certificates"], [expected_certificates_data])

    def test_get_certificates_user_not_found(self):
        """
        Test retrieval attempt with a non-existent national ID.

        Expected behavior:
            - Status code 404.
            - Return error message indicating user was not found.
        """
        url = reverse("certificates-api:v1:user-certificate-list", args=[1111111111])
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["error"],
            "User with the provided national ID was not found."
        )

    def test_get_certificates_forbidden_non_staff(self):
        """
        Test retrieval attempt by an authenticated non-staff user.

        Expected behavior:
            - Status code 403.
        """
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_certificates_unauthenticated(self):
        """
        Test retrieval attempt without valid authentication.

        Expected behavior:
            - Status code 401.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
