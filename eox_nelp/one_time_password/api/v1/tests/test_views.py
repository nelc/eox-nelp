"""This file contains all the test for the one_time_password API V1 views.py file.

Classes:
    GenerateOTPTestCase: Class to test GenerateOTP view
"""

from custom_reg_form.models import ExtraInfo
from ddt import data, ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from mock import patch
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.one_time_password import view_decorators
from eox_nelp.one_time_password.api.v1 import views
from eox_nelp.tests.mixins import POSTAuthenticatedTestMixin
from eox_nelp.tests.utils import get_cache_expiration_time

User = get_user_model()


@ddt
class GenerateOTPTestCase(POSTAuthenticatedTestMixin, APITestCase):
    """Test case for generate OTP view."""
    reverse_viewname = "one-time-password-api:v1:generate-otp"

    @data({}, {"not_phone_number": 3123123123})
    def test_generate_otp_without_right_payload(self, wrong_payload):
        """
        Test  the post request to generate otp is not running due missing keys in the payload sent.
        Expected behavior:
            - Check the response say is missing some keys.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, wrong_payload, format="json")

        self.assertDictEqual(response.json(), {"detail": "missing phone_number in data."})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        SMS_VENDOR_SEND_SMS_PATH="/test/sms/path",
        SMS_VENDOR_BASE_URL="http://test-sms-vendor.com",
    )
    @patch("eox_nelp.one_time_password.api.v1.views.SMSVendorApiClient")
    def test_generate_otp(self, sms_vendor_mock):
        """
        Test  the post request to generate otp.
        Expected behavior:
            - Check logging generation msg
            - Check the response say success otp generated.
            - Status code 201.
            - Check that in cache the OTP is stored(not None).
            - Check that the expiration OTP is less than default value 600s, and bigger than a prudent execution time.
            - Check the length of the OTP code is the default 8.
            - Check SMSVendorApiClient called with expected parameters.
        """
        payload = {"phone_number": "+573218995688"}
        sms_vendor_mock().send_sms.return_value = {
            'message': 'Operation completed successfully',
            'transaction_id': 'fxlms-4177f72b-2f36-4668-b86b-adasdasdasds3',
            'recipient': payload['phone_number'],
            'timestamp': '1721336004372'
        }
        url_endpoint = reverse(self.reverse_viewname)
        user_otp_key = f"{self.user.username}-{payload['phone_number']}"

        with self.assertLogs(views.__name__, level="INFO") as logs:
            response = self.client.post(url_endpoint, payload, format="json")

        otp_stored = cache.get(user_otp_key)
        expiration_otp = get_cache_expiration_time(user_otp_key)
        self.assertEqual(logs.output, [
            f"INFO:{views.__name__}:generating otp {user_otp_key[:-5]}*****"
        ])
        self.assertDictEqual(response.json(), {"message": "Success generate-otp!"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(otp_stored)
        self.assertTrue(500 < expiration_otp < 600)
        self.assertEqual(len(otp_stored), 8)
        sms_vendor_mock().send_sms.assert_called_with(
            payload['phone_number'],
            f"Futurex Phone Validation Code: {otp_stored}",
            "/test/sms/path"
        )

    @override_settings(
        SMS_VENDOR_SEND_SMS_PATH="/test/sms/path",
        SMS_VENDOR_BASE_URL="http://test-sms-vendor.com",
    )
    @patch("eox_nelp.one_time_password.api.v1.views.SMSVendorApiClient")
    def test_generate_otp_fails_sms_vendor(self, sms_vendor_mock):
        """
        Test  the post request to generate otp.
        Expected behavior:
            - Check logging generation
            - Check the response say success otp generated.
            - Status code 503.
            - Check that in cache the OTP is stored(not None).
            - Check SMSVendorApiClient called with expected parameters.
        """
        payload = {"phone_number": "+573218995699"}
        sms_vendor_mock().send_sms.return_value = {'error': True, 'message': 'Invalid response with status 400'}
        url_endpoint = reverse(self.reverse_viewname)
        user_otp_key = f"{self.user.username}-{payload['phone_number']}"

        with self.assertLogs(views.__name__, level="INFO") as logs:
            response = self.client.post(url_endpoint, payload, format="json")

        otp_stored = cache.get(user_otp_key)
        expiration_otp = get_cache_expiration_time(user_otp_key)
        self.assertEqual(logs.output, [
            f"INFO:{views.__name__}:generating otp {user_otp_key[:-5]}*****"
        ])
        self.assertDictEqual(response.json(), {"detail": "error with SMS Vendor communication"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIsNotNone(otp_stored)
        self.assertTrue(500 < expiration_otp < 600)
        self.assertEqual(len(otp_stored), 8)
        sms_vendor_mock().send_sms.assert_called_with(
            payload['phone_number'],
            f"Futurex Phone Validation Code: {otp_stored}",
            "/test/sms/path"
        )

    @override_settings(
        PHONE_VALIDATION_OTP_LENGTH=20,
        PHONE_VALIDATION_OTP_CHARSET="01",
        PHONE_VALIDATION_OTP_TIMEOUT=1200,
        SMS_VENDOR_SEND_SMS_PATH="/test/sms/path",
        SMS_VENDOR_BASE_URL="http://test-sms-vendor.com",
    )
    @patch("eox_nelp.one_time_password.api.v1.views.SMSVendorApiClient")
    def test_generate_otp_custom_settings(self, sms_vendor_mock):
        """
        Test  the post request to generate otp with custom settings.
        Expected behavior:
            - Check logging generation msg
            - Check the response say success otp generated..
            - Status code 201.
            - Check that in cache the OTP is stored(not None).
            - Check that the expiration OTP is less than settings value, and bigger than a prudent execution time.
            - Check the length of the OTP code is the settings value.
            - Check that the chars of setting value is presented in the otp code.
            - Check SMSVendorApiClient called with expected parameters.
        """
        payload = {"phone_number": "+9663218995688"}
        sms_vendor_mock().send_sms.return_value = {
            'message': 'Operation completed successfully',
            'transaction_id': 'fxlms-4177f72b-2f36-4668-b86b-adasdasdasds3',
            'recipient': payload['phone_number'],
            'timestamp': '1721336004372'
        }
        url_endpoint = reverse(self.reverse_viewname)
        user_otp_key = f"{self.user.username}-{payload['phone_number']}"

        with self.assertLogs(views.__name__, level="INFO") as logs:
            response = self.client.post(url_endpoint, payload, format="json")

        otp_stored = cache.get(user_otp_key)
        expiration_otp = get_cache_expiration_time(user_otp_key)
        self.assertEqual(logs.output, [
            f"INFO:{views.__name__}:generating otp {user_otp_key[:-5]}*****"
        ])
        self.assertDictEqual(response.json(), {"message": "Success generate-otp!"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(otp_stored)
        self.assertTrue(
            (settings.PHONE_VALIDATION_OTP_TIMEOUT - 100) < expiration_otp < settings.PHONE_VALIDATION_OTP_TIMEOUT
        )
        self.assertEqual(len(otp_stored), settings.PHONE_VALIDATION_OTP_LENGTH)
        self.assertIn(settings.PHONE_VALIDATION_OTP_CHARSET[0], otp_stored)
        sms_vendor_mock().send_sms.assert_called_with(
            payload['phone_number'],
            f"Futurex Phone Validation Code: {otp_stored}",
            "/test/sms/path"
        )


@ddt
class ValidateOTPTestCase(POSTAuthenticatedTestMixin, APITestCase):
    """Test case for validate OTP view."""
    reverse_viewname = "one-time-password-api:v1:validate-otp"

    def setUp(self):
        """Overrides setUp behavior to add extrainfo attribute
        """
        super().setUp()
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=self.user,
            arabic_name="مسؤل",
            national_id="1234578960",
            occupation="student",
        )

    def tearDown(self):
        """Clear cache after or mocks each test case. Clean extrainfo values."""
        cache.clear()
        ExtraInfo.objects.all().delete()  # pylint: disable=no-member

    @data({}, {"not_phone_number": 3123123123}, {"not_one_time_password": 12345678, "phone_number": 3123123123})
    def test_validate_otp_without_right_payload(self, wrong_payload):
        """
        Test  the post request to validate otp is not running due missing keys in the payload sent.
        Expected behavior:
            - Check the response say is missing some keys.
            - Status code 400.
        """
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, wrong_payload, format="json")

        self.assertDictEqual(response.json(), {"detail": "missing phone_number or one_time_password in data."})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_otp_without_right_validation_code(self):
        """
        Test  the post request to validate otp with wrong validation code.

        Expected behavior:
            - Check logging validation msg
            - Status code 403.
            - Cache related with the OTP is different from None
        """
        correct_otp = "correct17"
        payload = {"phone_number": 3219990000, "one_time_password": "password"}
        url_endpoint = reverse(self.reverse_viewname)
        user_otp_key = f"{self.user.username}-{payload['phone_number']}"
        cache.set(user_otp_key, correct_otp, timeout=600)

        with self.assertLogs(view_decorators.__name__, level="INFO") as logs:
            response = self.client.post(url_endpoint, payload, format="json")

        self.assertEqual(logs.output, [
            f"INFO:{view_decorators.__name__}:validating otp for {user_otp_key[:-5]}*****"
        ])
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNotNone(cache.get(f"{self.user.username}-{payload['phone_number']}"))

    def test_validate_right_otp_code(self):
        """
        Test the post request to validate otp with right data.

        Expected behavior:
            - Check loggin validation msg
            - Check the response say success validate-otp.
            - Status code 200.
            - Cache related with the OTP has been deleted
        """
        correct_otp = "correct26"
        payload = {"phone_number": 3219990000, "one_time_password": correct_otp}
        url_endpoint = reverse(self.reverse_viewname)
        user_otp_key = f"{self.user.username}-{payload['phone_number']}"
        cache.set(user_otp_key, correct_otp, timeout=600)

        with self.assertLogs(view_decorators.__name__, level="INFO") as logs:
            response = self.client.post(url_endpoint, payload, format="json")

        self.assertEqual(logs.output, [
            f"INFO:{view_decorators.__name__}:validating otp for {user_otp_key[:-5]}*****",
        ])
        self.assertDictEqual(response.json(), {"message": "Valid OTP code"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(cache.get(f"{self.user.username}-{payload['phone_number']}"))

    def test_validate_right_otp_code_with_extra_info(self):
        """
        Test the post request to validate otp with right data with a user with extrainfo foreign model.

        Expected behavior:
            - Check everything from test `test_validate_right_otp_code`
            - extrainfo attr of user in is_phone_validated is True.
        """
        self.test_validate_right_otp_code()

        self.user.extrainfo.refresh_from_db()
        self.assertTrue(self.user.extrainfo.is_phone_validated)
