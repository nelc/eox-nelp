"""
This file contains all the tests for the user_profile API V1 views.py file.

Test Cases:
    - UpdateUserDataTestCase: Tests for update_user_data view.
    - GetValidatedUserFieldsTestCase: Tests for get_validated_user_fields view.
"""


from unittest.mock import patch

from custom_reg_form.models import ExtraInfo
from ddt import ddt
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from eox_nelp.edxapp_wrapper.user_api import accounts, errors
from eox_nelp.tests.mixins import POSTAuthenticatedTestMixin

User = get_user_model()


@ddt
class UpdateUserDataTestCase(POSTAuthenticatedTestMixin, APITestCase):
    """Test case for update user data view."""
    reverse_viewname = "user-profile-api:v1:update-user-data"

    def setUp(self):
        """Default every user to holding no institution role; lock tests switch it on."""
        super().setUp()
        patcher = patch("eox_nelp.user_profile.api.v1.helpers.holds_institution_role", return_value=False)
        self.holds_role_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def create_extra_info(self, national_id):
        """Give the user a complete ExtraInfo, so ExtraInfoForm validates on later updates."""
        return ExtraInfo.objects.create(  # pylint: disable=no-member
            user=self.user, national_id=national_id, arabic_name="فيدر", occupation="student",
        )

    def tearDown(self):
        """Reset Mocks"""
        accounts.reset_mock()
        accounts.api.update_account_settings.side_effect = None

    @override_settings(
        ENABLE_OTP_VALIDATION=False,
        USE_PEARSON_ENGINE_SERVICE=True,
    )
    @patch("eox_nelp.user_profile.api.v1.views.real_time_import_task_v2")
    def test_update_fields_successfully(self, cdd_task_mock):
        """
        Test that the request completes its execution successfully.

        Expected behavior:
            - Check the response says that the field has been updated.
            - Status code 200.
            - Check that update_account_settings method has called once.
            - Check cdd_task async task is called user.id
        """
        payload = {"phone_number": "+573219990000", "one_time_password": "correct26"}
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"message": "User's fields has been updated successfully"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)
        cdd_task_mock.delay.assert_called_with(user_id=self.user.id, action_name="cdd")

    @override_settings(ENABLE_OTP_VALIDATION=False)
    @patch("eox_nelp.user_profile.api.v1.views.real_time_import_task_v2")
    def test_account_validation_error(self, cdd_task_mock):
        """
        Test that a bad request is returned when an AccountValidationError is raised.

        Expected behavior:
            - Check the response contains fields_errors.
            - Status code 400.
            - Check that update_account_settings method has called once.
            - Check cdd_task async is not called.
        """
        payload = {"phone_number": "+573219990000", "one_time_password": "correct26"}
        url_endpoint = reverse(self.reverse_viewname)
        accounts.api.update_account_settings.side_effect = errors.AccountValidationError(
            field_errors="Invalid phone number",
        )

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"field_errors": "Invalid phone number"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)
        cdd_task_mock.delay.assert_not_called()

    @override_settings(ENABLE_OTP_VALIDATION=False)
    @patch("eox_nelp.user_profile.api.v1.views.real_time_import_task_v2")
    def test_account_update_error(self, cdd_task_mock):
        """
        Test that a bad request is returned when an AccountUpdateError is raised.

        Expected behavior:
            - Check the response contains developer and user message.
            - Status code 400.
            - Check that update_account_settings method has called once.
            - Check cdd_task async is not called.
        """
        payload = {"phone_number": "+573219990000", "one_time_password": "correct26"}
        url_endpoint = reverse(self.reverse_viewname)
        expected_response = {
            "developer_message": "The testing method failed",
            "user_message": "You user wasn't updated",
        }
        accounts.api.update_account_settings.side_effect = errors.AccountUpdateError(
            **expected_response,
        )

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), expected_response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)
        cdd_task_mock.delay.assert_not_called()

    @override_settings(
        ENABLE_OTP_VALIDATION=False,
        EXTRA_ACCOUNT_USER_FIELDS=["first_name", "last_name"],
        USE_PEARSON_ENGINE_SERVICE=True,
    )
    @patch("eox_nelp.user_profile.api.v1.views.real_time_import_task_v2")
    def test_account_update_extra_fields(self, cdd_task_mock):
        """
        Test that extra account user fields has been set.

        Expected behavior:
            - Check the response says that the field has been updated.
            - Status code 200.
            - Check that update_account_settings method has called once.
            - Check that user first_name has been updated.
            - Check that user last_name has been updated.
            - Check cdd_task async task is called with user.id
        """
        payload = {
            "first_name": "Anakin",
            "last_name": "Skywalker",
            "one_time_password": "correct26",
        }
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"message": "User's fields has been updated successfully"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)
        self.assertEqual(self.user.first_name, payload["first_name"])
        self.assertEqual(self.user.last_name, payload["last_name"])
        cdd_task_mock.delay.assert_called_with(user_id=self.user.id, action_name="cdd")

    @override_settings(
        ENABLE_OTP_VALIDATION=False,
        USER_PROFILE_API_EXTRA_INFO_FIELDS=[
            "arabic_name",
            "arabic_first_name",
            "arabic_last_name",
            "national_id",
            "occupation",
        ],
        USE_PEARSON_ENGINE_SERVICE=True,
    )
    @patch("eox_nelp.user_profile.api.v1.views.real_time_import_task_v2")
    def test_update_extra_info_fields(self, cdd_task_mock):
        """
        Test that extra account user fields has been set.

        Expected behavior:
            - Check the response says that the field has been updated.
            - Status code 200.
            - Check that update_account_settings method has called once.
            - Check that user extra info arabic_first_name has been updated.
            - Check that user extra info arabic_last_name has been updated.
        """
        payload = {
            "arabic_name": "سكاي ووكر أناكين",
            "arabic_first_name": "أناكين",
            "arabic_last_name": "سكاي ووكر",
            "national_id": "1234512345",
            "occupation": "student",
        }
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"message": "User's fields has been updated successfully"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)
        self.assertEqual(self.user.extrainfo.arabic_first_name, payload["arabic_first_name"])
        self.assertEqual(self.user.extrainfo.arabic_last_name, payload["arabic_last_name"])
        cdd_task_mock.delay.assert_called_with(user_id=self.user.id, action_name="cdd")

    @override_settings(ENABLE_OTP_VALIDATION=False)
    def test_invalid_phone_number(self):
        """
        Test that a bad request is returned when an invalid phone number is provided.

        Expected behavior:
            - Check the response contains fields_errors.
            - Status code 400.
            - Check that update_account_settings method is not called.
        """
        payload = {"phone_number": "+573219990", "one_time_password": ""}
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"field_errors": {"phone_number": ["Invalid phone number"]}})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        accounts.api.update_account_settings.assert_not_called()

    @override_settings(ENABLE_OTP_VALIDATION=False, USER_PROFILE_API_VALIDATE_PHONE_NUMBER=False)
    def test_allow_invalid_phone_number(self):
        """
        Test that the request completes its execution successfully when an invalid phone numer is
        provided and USER_PROFILE_API_VALIDATE_PHONE_NUMBER is False.

        Expected behavior:
            - Check the response says that the field has been updated.
            - Status code 200.
            - Check that update_account_settings method has called once.
        """
        payload = {"phone_number": "+573219990", "one_time_password": "correct26"}
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.post(url_endpoint, payload, format="json")

        self.assertDictEqual(response.json(), {"message": "User's fields has been updated successfully"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        accounts.api.update_account_settings.assert_called_once_with(self.user, payload)

    @override_settings(ENABLE_OTP_VALIDATION=False, USER_PROFILE_API_EXTRA_INFO_FIELDS=["national_id"])
    def test_national_id_change_locked_for_institution_role(self):
        """
        Test that an account holding an institution role cannot change its national_id.

        Expected behavior:
            - Status code 400 with a national_id field error.
            - The stored national_id is unchanged.
        """
        self.create_extra_info("1000000301")
        self.holds_role_mock.return_value = True

        response = self.client.post(reverse(self.reverse_viewname), {"national_id": "1000000302"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("national_id", response.json()["field_errors"])
        self.user.extrainfo.refresh_from_db()
        self.assertEqual(self.user.extrainfo.national_id, "1000000301")

    @override_settings(ENABLE_OTP_VALIDATION=False, USER_PROFILE_API_EXTRA_INFO_FIELDS=["national_id"])
    def test_national_id_first_set_locked_for_institution_role(self):
        """
        Test that an account holding an institution role cannot set a national_id for the first time.

        Expected behavior:
            - Status code 400 with a national_id field error.
            - No national_id is stored.
        """
        self.holds_role_mock.return_value = True

        response = self.client.post(reverse(self.reverse_viewname), {"national_id": "1000000303"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("national_id", response.json()["field_errors"])
        self.assertFalse(ExtraInfo.objects.filter(national_id="1000000303").exists())  # pylint: disable=no-member

    @override_settings(ENABLE_OTP_VALIDATION=False, USER_PROFILE_API_EXTRA_INFO_FIELDS=["national_id"])
    def test_same_national_id_allowed_for_institution_role(self):
        """
        Test that re-sending the current national_id is allowed, since profile forms submit every field.

        Expected behavior:
            - Status code 200.
            - The role check is not needed.
        """
        self.create_extra_info("1000000304")
        self.holds_role_mock.return_value = True

        response = self.client.post(reverse(self.reverse_viewname), {"national_id": " 1000000304 "}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.holds_role_mock.assert_not_called()

    @override_settings(ENABLE_OTP_VALIDATION=False, USER_PROFILE_API_EXTRA_INFO_FIELDS=["national_id"])
    def test_national_id_change_allowed_without_institution_role(self):
        """
        Test that a learner without an institution role can still correct their national_id.

        Expected behavior:
            - Status code 200.
            - The new national_id is stored.
        """
        self.create_extra_info("1000000305")

        response = self.client.post(reverse(self.reverse_viewname), {"national_id": "1000000306"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.extrainfo.refresh_from_db()
        self.assertEqual(self.user.extrainfo.national_id, "1000000306")

    @override_settings(
        ENABLE_OTP_VALIDATION=False,
        USER_PROFILE_API_EXTRA_INFO_FIELDS=["national_id", "arabic_first_name"],
    )
    def test_other_extra_info_fields_update_for_institution_role(self):
        """
        Test that the lock only concerns national_id.

        Expected behavior:
            - Status code 200.
            - arabic_first_name is updated for an account holding an institution role.
        """
        self.create_extra_info("1000000307")
        self.holds_role_mock.return_value = True

        response = self.client.post(reverse(self.reverse_viewname), {"arabic_first_name": "أناكين"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.extrainfo.refresh_from_db()
        self.assertEqual(self.user.extrainfo.arabic_first_name, "أناكين")


class GetValidatedUserFieldsTestCase(APITestCase):
    """Test case for get_validated_user_fields view."""

    reverse_viewname = "user-profile-api:v1:validated-fields"

    def setUp(self):
        """Set up a test user and authenticate the client."""
        self.user = User.objects.create(username="testuser")
        self.client.force_authenticate(user=self.user)

    @patch("eox_nelp.user_profile.api.v1.views.validate_required_user_fields")
    def test_get_validated_user_fields_successfully(self, mock_validate_required_user_fields):
        """
        Test that the view returns the expected validated fields.

        Expected behavior:
            - The function should return a JSON response with validated fields.
            - Status code 200.
            - The function should call validate_required_user_fields with the correct user instance.
        """
        expected_response = {
            "account": {"first_name": [], "last_name": []},
            "profile": {"city": [], "country": [], "phone_number": ["Empty field"], "mailing_address": []},
            "extra_info": {"arabic_name": [], "arabic_first_name": [], "arabic_last_name": []},
        }
        mock_validate_required_user_fields.return_value = expected_response
        url_endpoint = reverse(self.reverse_viewname)

        response = self.client.get(url_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.json(), expected_response)
        mock_validate_required_user_fields.assert_called_once_with(self.user)
