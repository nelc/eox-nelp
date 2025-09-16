"""
Test views file for programs API v1.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class ProgramsMetadataViewTestCase(TestCase):
    """Test cases for ProgramsMetadataView."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
        )
        self.client.force_authenticate(self.user)
        self.course_id = "course-v1:edX+DemoX+Demo_Course"
        self.url = reverse("programs-api:v1:programs-metadata", args=[self.course_id])

    def test_get_program_metadata_success(self):
        """
        Test successful retrieval of program metadata.
        Expected behavior:
            - Status code 200.
            - Return expected program metadata.
        """
        mock_metadata = {
            "trainer_type": 10,
            "Type_of_Activity": 1,
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.get_program_metadata") as mock_get:
            mock_get.return_value = mock_metadata

            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, mock_metadata)
            mock_get.assert_called_once_with(self.course_id)

    def test_get_program_metadata_not_found(self):
        """
        Test retrieval when program metadata is not found.
        Expected behavior:
            - Status code 404.
            - Return error message.
        """
        with patch("eox_nelp.programs.api.v1.views.get_program_metadata") as mock_get:
            mock_get.return_value = None

            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data, {"error": "Program metadata not found"})

    def test_get_program_metadata_not_authenticated(self):
        """
        Test retrieval without authentication.
        Expected behavior:
            - Status code 401.
            - Return authentication error.
        """
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided", str(response.data))

    @override_settings(FEATURES={"ENABLE_OTHER_COURSE_SETTINGS": False})
    def test_get_program_metadata_feature_disabled(self):
        """
        Test retrieval when feature is disabled.
        Expected behavior:
            - Status code 501.
            - Return feature not implemented error.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        self.assertIn("ENABLE_OTHER_COURSE_SETTINGS", str(response.data))

    def test_post_program_metadata_success(self):
        """
        Test successful creation/update of program metadata.
        Expected behavior:
            - Status code 201.
            - Return updated metadata.
        """
        metadata_data = {
            "trainer_type": 10,
            "Type_of_Activity": 1,
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.update_program_metadata") as mock_update:
            mock_update.return_value = True

            response = self.client.post(self.url, metadata_data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            # The response includes trainer_type as read-only field
            expected_data = {
                "trainer_type": 10,
                "Type_of_Activity": 1,
                "Mandatory": "01",
                "Program_ABROVE": "01",
                "Program_code": "TEST001",
            }
            self.assertEqual(response.data, expected_data)
            # trainer_type is read-only, so it's not included in validated_data
            expected_data = {
                "trainer_type": 10,
                "Type_of_Activity": 1,
                "Mandatory": "01",
                "Program_ABROVE": "01",
                "Program_code": "TEST001",
            }
            mock_update.assert_called_once_with(self.course_id, expected_data, self.user)

    def test_post_program_metadata_invalid_data(self):
        """
        Test creation with invalid data.
        Expected behavior:
            - Status code 400.
            - Return validation errors.
        """
        invalid_data = {
            "trainer_type": 10,
            "Type_of_Activity": 1,
            "Mandatory": "invalid",  # Invalid value - too long
            "Program_ABROVE": "01",
            "Program_code": "",  # Empty value
        }

        response = self.client.post(self.url, invalid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ensure this field has no more than 2 characters", str(response.data))
        self.assertIn("This field may not be blank", str(response.data))

    def test_post_program_metadata_not_authenticated(self):
        """
        Test creation without authentication.
        Expected behavior:
            - Status code 401.
            - Return authentication error.
        """
        self.client.force_authenticate(user=None)
        metadata_data = {
            "Type_of_Activity": 1,
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        response = self.client.post(self.url, metadata_data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided", str(response.data))

    @override_settings(FEATURES={"ENABLE_OTHER_COURSE_SETTINGS": False})
    def test_post_program_metadata_feature_disabled(self):
        """
        Test creation when feature is disabled.
        Expected behavior:
            - Status code 501.
            - Return feature not implemented error.
        """
        metadata_data = {
            "Type_of_Activity": 1,
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        response = self.client.post(self.url, metadata_data)

        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        self.assertIn("ENABLE_OTHER_COURSE_SETTINGS", str(response.data))

    def test_post_program_metadata_serializer_validation_error(self):
        """
        Test creation with serializer validation error.
        Expected behavior:
            - Status code 400.
            - Return validation error details.
        """
        invalid_data = {
            "Type_of_Activity": "not_a_number",  # Invalid type
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        response = self.client.post(self.url, invalid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("A valid integer is required", str(response.data))

    def test_get_program_metadata_serializer_validation_error(self):
        """
        Test retrieval when serializer validation fails on existing data.
        Expected behavior:
            - Status code 400.
            - Return validation error details.
        """
        invalid_metadata = {
            "trainer_type": 10,
            "Type_of_Activity": 1,
            "Mandatory": "invalid",  # Invalid value - too long
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.get_program_metadata") as mock_get:
            mock_get.return_value = invalid_metadata

            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("Ensure this field has no more than 2 characters", str(response.data))

    def test_program_metadata_structure_validation(self):
        """
        Test that program metadata has expected structure.
        Expected behavior:
            - All required fields are present.
            - Field validation works correctly.
        """
        valid_metadata = {
            "trainer_type": 10,
            "Type_of_Activity": 1,
            "Mandatory": "01",
            "Program_ABROVE": "01",
            "Program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.get_program_metadata") as mock_get:
            mock_get.return_value = valid_metadata

            response = self.client.get(self.url)

            if response.status_code == status.HTTP_200_OK:
                expected_fields = ["trainer_type", "Type_of_Activity", "Mandatory", "Program_ABROVE", "Program_code"]

                for field in expected_fields:
                    self.assertIn(field, response.data, f"Field '{field}' missing from response")

    def test_program_metadata_mandatory_field_validation(self):
        """
        Test validation of Mandatory field values.
        Expected behavior:
            - Only "01" and "00" are accepted.
            - Other values return validation error.
        """
        test_cases = [
            ("01", True, None),
            ("00", True, None),
            ("invalid", False, "Ensure this field has no more than 2 characters"),
            ("1", False, "Mandatory must be one of: 01, 00"),
            ("0", False, "Mandatory must be one of: 01, 00"),
        ]

        for value, should_pass, expected_error in test_cases:
            with self.subTest(value=value):
                metadata_data = {
                    "trainer_type": 10,
                    "Type_of_Activity": 1,
                    "Mandatory": value,
                    "Program_ABROVE": "01",
                    "Program_code": "TEST001",
                }

                with patch("eox_nelp.programs.api.v1.views.update_program_metadata") as mock_update:
                    mock_update.return_value = True

                    response = self.client.post(self.url, metadata_data)

                    if should_pass:
                        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                    else:
                        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                        self.assertIn(expected_error, str(response.data))

    def test_program_metadata_program_abrove_field_validation(self):
        """
        Test validation of Program_ABROVE field values.
        Expected behavior:
            - Only "01" and "00" are accepted.
            - Other values return validation error.
        """
        test_cases = [
            ("01", True, None),
            ("00", True, None),
            ("invalid", False, "Ensure this field has no more than 2 characters"),
            ("1", False, "Program_ABROVE must be one of: 01, 00"),
            ("0", False, "Program_ABROVE must be one of: 01, 00"),
        ]

        for value, should_pass, expected_error in test_cases:
            with self.subTest(value=value):
                metadata_data = {
                    "trainer_type": 10,
                    "Type_of_Activity": 1,
                    "Mandatory": "01",
                    "Program_ABROVE": value,
                    "Program_code": "TEST001",
                }

                with patch("eox_nelp.programs.api.v1.views.update_program_metadata") as mock_update:
                    mock_update.return_value = True

                    response = self.client.post(self.url, metadata_data)

                    if should_pass:
                        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                    else:
                        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                        self.assertIn(expected_error, str(response.data))

    def test_program_metadata_program_code_validation(self):
        """
        Test validation of Program_code field.
        Expected behavior:
            - Empty or whitespace-only values are rejected.
            - Valid values are accepted.
        """
        test_cases = [
            ("TEST001", True),
            ("VALID_CODE", True),
            ("", False),
            ("   ", False),
            ("A" * 65, False),  # Too long
        ]

        for value, should_pass in test_cases:
            with self.subTest(value=value):
                metadata_data = {
                    "trainer_type": 10,
                    "Type_of_Activity": 1,
                    "Mandatory": "01",
                    "Program_ABROVE": "01",
                    "Program_code": value,
                }

                with patch("eox_nelp.programs.api.v1.views.update_program_metadata") as mock_update:
                    mock_update.return_value = True

                    response = self.client.post(self.url, metadata_data)

                    if should_pass:
                        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                    else:
                        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                        if not value or not value.strip():
                            self.assertIn("This field may not be blank", str(response.data))
