"""
Unit tests for Certificates API v1 views.
"""
from datetime import datetime, timezone

from custom_reg_form.models import ExtraInfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from mock import patch
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.edxapp_wrapper.certificates import api as certificates_api
from eox_nelp.edxapp_wrapper.certificates import utils as certificates_utils
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview, get_course_overviews
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.tests.utils import set_key_values

User = get_user_model()
GeneratedCertificate = get_generated_certificate()

NATIONAL_ID = "1234567890"
CERTIFICATE_ID = "2c97649425bb49189470f05bf7d98c1a"
COURSE_ID = "course-v1:test+Cx105+2022_T4"
ISSUE_DATE = datetime(2024, 5, 29, 17, 24, tzinfo=timezone.utc)
ENGLISH_NAME = "Test Student"
ARABIC_NAME = "مسؤل"


class UserCertificateListViewTests(APITestCase):
    """
    Test suite for the UserCertificateListView API view.
    """

    def setUp(self):
        """
        Set up the test data and mock clients for the test suite.
        """
        self.url = reverse("certificates-api:v1:user-certificate-list", args=[NATIONAL_ID])
        self.detail_url = reverse("certificates-api:v1:user-certificate-detail", args=[CERTIFICATE_ID])
        self.student, _ = User.objects.get_or_create(
            username="student",
            email="student@example.com",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=self.student,
            arabic_name=ARABIC_NAME,
            national_id=NATIONAL_ID,
            occupation="student",
        )
        CourseOverview.objects.get_or_create(
            id=CourseKey.from_string(COURSE_ID),
            org="test",
        )
        GeneratedCertificate.objects.create(**{
            'user': self.student,
            'course_id': CourseKey.from_string(COURSE_ID),
            'grade': '71.0',
            'status': 'downloadable',
            'mode': 'honor',
            "verify_uuid": CERTIFICATE_ID,

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
        certificates_api.display_date_for_certificate.return_value = ISSUE_DATE
        certificates_utils.get_certificate_url.return_value = f"/certificates/{CERTIFICATE_ID}"
        get_course_overviews.return_value = [{"display_name": "TestingCourse"}]

    @staticmethod
    def expected_certificate_data():
        """
        Build the expected serialized representation of the certificate created on setUp.

        Returns:
            dict: expected certificate payload.
        """
        return {
            "certificate_id": CERTIFICATE_ID,
            "tenant": "test.openedx.io",
            "org": "test",
            "course_id": COURSE_ID,
            "course_name": "TestingCourse",
            "status": "downloadable",
            "mode": "honor",
            "issue_date": ISSUE_DATE.isoformat(),
            "certificate_url": f"http://test.openedx.io/certificates/{CERTIFICATE_ID}",
        }

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificates_success(self):
        """
        Test successful retrieval of user certificates by national ID.

        Expected behavior:
            - Status code 200.
            - Return expected username.
            - Return expected national ID.
            - Return expected english and arabic names.
            - Return expected serialized certificates.
        """
        self.client.force_authenticate(user=self.staff_user)
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student")
        self.assertEqual(response.data["national_id"], NATIONAL_ID)
        self.assertEqual(response.data["english_name"], ENGLISH_NAME)
        self.assertEqual(response.data["arabic_name"], ARABIC_NAME)
        self.assertEqual(response.data["certificates"], [self.expected_certificate_data()])

    @override_settings(SITE_NAME="test.openedx.io", LMS_ROOT_URL="http://test.openedx.io/")
    def test_get_certificate_by_certificate_id_success(self):
        """
        Test successful retrieval of a single certificate by its certificate ID.

        Expected behavior:
            - Status code 200.
            - Return the owner details of the matched certificate.
            - Return only the certificate matching the requested certificate ID.
        """
        self.client.force_authenticate(user=self.staff_user)
        GeneratedCertificate.objects.create(**{
            'user': self.student,
            'course_id': CourseKey.from_string("course-v1:test+Cx106+2022_T4"),
            'grade': '80.0',
            'status': 'downloadable',
            'mode': 'honor',
            "verify_uuid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        })
        configuration_helpers.get_value_for_org.side_effect = [settings.SITE_NAME, settings.LMS_ROOT_URL]

        with patch.object(User, "profile", set_key_values({"name": ENGLISH_NAME}), create=True):
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "student")
        self.assertEqual(response.data["national_id"], NATIONAL_ID)
        self.assertEqual(response.data["english_name"], ENGLISH_NAME)
        self.assertEqual(response.data["arabic_name"], ARABIC_NAME)
        self.assertEqual(response.data["certificates"], [self.expected_certificate_data()])

    def test_get_certificate_by_certificate_id_not_found(self):
        """
        Test retrieval attempt with a certificate ID that matches no certificate.

        Expected behavior:
            - Status code 404.
            - Return error message indicating the certificate was not found.
        """
        url = reverse("certificates-api:v1:user-certificate-detail", args=["f" * 32])
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data["error"],
            "Certificate with the provided certificate ID was not found."
        )

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

    def test_get_certificate_by_certificate_id_forbidden_non_staff(self):
        """
        Test certificate ID retrieval attempt by an authenticated non-staff user.

        Expected behavior:
            - Status code 403.
        """
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_certificates_unauthenticated(self):
        """
        Test retrieval attempt without valid authentication.

        Expected behavior:
            - Status code 401.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
