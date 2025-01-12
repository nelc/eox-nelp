"""This file contains all the test for certificates api client file.

Classes:
    TestExternalCertificatesApiClient: Test for eox-nelp/api_clients/certificates.py.
"""
import unittest

from django.test import override_settings
from django.utils import timezone
from mock import Mock, patch

from eox_nelp.api_clients.certificates import ExternalCertificatesApiClient
from eox_nelp.api_clients.tests import TestBasicAuthApiClientMixin
from eox_nelp.signals.utils import generate_reference_id


class TestExternalCertificatesApiClient(TestBasicAuthApiClientMixin, unittest.TestCase):
    """Tests ExternalCertificatesApiClient"""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.api_class = ExternalCertificatesApiClient

    @patch.object(ExternalCertificatesApiClient, "make_post")
    @patch.object(ExternalCertificatesApiClient, "_authenticate", Mock)
    def test_create_certificate(self, post_mock):
        """Test successful post request.

        Expected behavior:
            - Response is the expected value
        """
        expected_value = {
            "status": {"success": True, "message": "successful", "code": 1}
        }
        post_mock.return_value = expected_value
        user = {
            "national_id": "1222555888",
            "english_name": " Testing",
            "arabic_name": "اختبارات",
        }
        course_id = "course-v1:FutureX+guide+2023"
        data = {
            "id": "124ABC",
            "reference_id": generate_reference_id(user["national_id"], course_id),
            "created_at": timezone.now(),
            "expiration_date": timezone.now() + timezone.timedelta(days=365),
            "grade": 10,
            "is_passing": True,
            "user": user,
            "group_code": "ABC123",
        }
        api_client = self.api_class()

        response = api_client.create_external_certificate(data)

        self.assertDictEqual(response, expected_value)

    @patch.object(ExternalCertificatesApiClient, "_authenticate", Mock)
    def test_failed_create_certificate(self):
        """Test when the mandatory fields has not been sent.

        Expected behavior:
            - Raise KeyError exception.
        """
        data = {}
        api_client = self.api_class()

        self.assertRaises(KeyError, api_client.create_external_certificate, data)

    @override_settings(EXTERNAL_CERTIFICATES_EXTRA_HEADERS={"HTTP_CUSTOM_HEADER": "ABC123"})
    def test_extra_headers(self):
        """Test if the extra header has been added to the session

        Expected behavior:
            - Custom Header in session headers.
        """
        api_client = self.api_class()

        self.assertEqual(api_client.session.headers["HTTP_CUSTOM_HEADER"], "ABC123")
