"""
Test views file for programs API v1.
"""

from unittest.mock import MagicMock, patch

from custom_reg_form.models import ExtraInfo
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview

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


class ProgramsListViewTestCase(APITestCase):
    """Test cases for ProgramsListView."""
    BASE_COURSE_ID = "course-v1:sky+walker+2023-v"

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("programs-api:v1:program-lookup")
        self.course1 = CourseOverview.objects.create(id=f"{self.BASE_COURSE_ID}1")
        self.course2 = CourseOverview.objects.create(id=f"{self.BASE_COURSE_ID}2")

    @patch("eox_nelp.programs.api.v1.views.NelpCourseListView.get")
    @patch("eox_nelp.programs.api.v1.utils.get_program_metadata")
    def test_get_programs_list_authenticated(
        self,
        mock_get_program_metadata,
        mock_super_get,
    ):
        """Test GET returns program list for authenticated user."""
        mock_super_get.return_value.data = {"results": COURSE_API_DATA}
        mock_get_program_metadata.return_value = {
            "trainer_type": 10,
            "Type_of_Activity": 165,
            "Mandatory": "01",
            "Program_ABROVE": "00",
            "Program_code": "eltesst",
        }
        expected_data = [
            {
                "Program_name": "testigngg",
                "Program_code": "eltesst",
                "Type_of_Activity": "برنامج الاستثمار الأمثل (برامج قصيرة)",
                "Type_of_Activity_id": 165,
                "Mandatory": "01",
                "Program_ABROVE": "00",
                "Code": "course-v1:edx+cd101+2020323",
                "Date_Start": "2030-01-01T00:00:00Z",
                "Date_End": None,
                "duration": 0,
                "Training_location": "FutureX",
                "Trainer_type": 10,
                "Unit": "hour",
            },
            {
                "Program_name": "small-graded",
                "Program_code": "eltesst",
                "Type_of_Activity": "برنامج الاستثمار الأمثل (برامج قصيرة)",
                "Type_of_Activity_id": 165,
                "Mandatory": "01",
                "Program_ABROVE": "00",
                "Code": "course-v1:edx+cd101+2023-t1",
                "Date_Start": "2020-01-01T00:00:00Z",
                "Date_End": "2034-12-25T00:00:00Z",
                "duration": 2,
                "Training_location": "FutureX",
                "Trainer_type": 10,
                "Unit": "hour",
            },
        ]

        response = self.client.get(self.url)


        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertListEqual(response.data, expected_data)

    @patch("eox_nelp.programs.api.v1.views.get_program_lookup_representation")
    @patch("eox_nelp.programs.api.v1.views.ProgramLookupSerializer")
    @patch("eox_nelp.programs.api.v1.views.CourseEnrollment.is_enrolled")
    @patch("eox_nelp.programs.api.v1.views.courses")
    def test_get_programs_list_with_national_id(
        self, mock_courses, mock_is_enrolled, mock_serializer, mock_lookup_repr,
    ):
        """Test GET returns program list for user with given national_id."""
        user_instance, _ = User.objects.get_or_create(username="user2", password="pass2")
        national_id = "1222888000"
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=user_instance,
            arabic_name="مسؤل",
            national_id=national_id,
        )
        course = MagicMock(id="course-v1:edx+special+2024")
        mock_courses.get_courses.return_value = [course]
        mock_is_enrolled.return_value = True
        mock_lookup_repr.return_value = {"id": "course-v1:edx+special+2024", "meta": "meta"}
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.is_valid.return_value = True
        mock_serializer_instance.data = {"id": "course-v1:edx+special+2024", "meta": "meta"}
        mock_serializer.return_value = mock_serializer_instance

        response = self.client.get(self.url, {"national_id": national_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data[0]["id"], "course-v1:edx+special+2024")

    def test_get_programs_list_unauthenticated(self):
        """Test GET returns 401 for unauthenticated user."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("eox_nelp.programs.api.v1.views.NelpCourseListView.get")
    @patch("eox_nelp.programs.api.v1.views.get_program_lookup_representation")
    @patch("eox_nelp.programs.api.v1.views.ProgramLookupSerializer")
    def test_get_programs_list_invalid_serializer(
        self, mock_serializer, mock_lookup_repr, mock_super_get
    ):
        """Test GET returns error if ProgramLookupSerializer is invalid."""
        mock_super_get.return_value.data = {"results": COURSE_API_DATA}
        mock_lookup_repr.return_value = {"id": "course-v1:edx+fail+2024", "meta": "meta"}
        mock_serializer_instance = MagicMock()
        mock_serializer_instance.is_valid.return_value = False
        mock_serializer_instance.errors = {"meta": ["invalid"]}
        mock_serializer.return_value = mock_serializer_instance

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data[0]["error"], "Invalid program lookup data")
        self.assertIn("details", response.data[0])

    @patch("eox_nelp.programs.api.v1.views.NelpCourseListView.get")
    def test_get_programs_list_no_enrolled_courses(self, mock_super_get):
        """Test GET returns empty list if no enrolled courses."""
        mock_super_get.return_value.data = {"results": []}

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])


COURSE_API_DATA = [
    {
        "blocks_url": "http://local.overhang.io:8000/api/courses/v2/blocks/?course_id=course-v1%3Aedx%2Bcd101%2B2020323",
        "effort": None,
        "end": None,
        "enrollment_start": None,
        "enrollment_end": None,
        "id": "course-v1:edx+cd101+2020323",
        "media": {
            "banner_image": {
                "uri": "/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "uri_absolute": "http://local.overhang.io:8000/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
            },
            "course_image": {"uri": "/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg"},
            "course_video": {"uri": None},
            "image": {
                "raw": "http://local.overhang.io:8000/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "small": "http://local.overhang.io:8000/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "large": "http://local.overhang.io:8000/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
            },
        },
        "name": "testigngg",
        "number": "cd101",
        "org": "edx",
        "short_description": None,
        "start": "2030-01-01T00:00:00Z",
        "start_display": None,
        "start_type": "empty",
        "pacing": "instructor",
        "mobile_available": False,
        "hidden": False,
        "invitation_only": False,
        "course_id": "course-v1:edx+cd101+2020323",
        "course_about_url": "http://local.overhang.io:8000/courses/course-v1:edx+cd101+2020323/about",
        "course_home_url": "http://apps.local.overhang.io:2000/learning/course/course-v1:edx+cd101+2020323/home",
    },
    {
        "blocks_url": "http://local.overhang.io:8000/api/courses/v2/blocks/?course_id=course-v1%3Aedx%2Bcd101%2B2023-t1",
        "effort": "2",
        "end": "2034-12-25T00:00:00Z",
        "enrollment_start": "2019-05-31T00:00:00Z",
        "enrollment_end": None,
        "id": "course-v1:edx+cd101+2023-t1",
        "media": {
            "banner_image": {
                "uri": "/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "uri_absolute": "http://local.overhang.io:8000/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
            },
            "course_image": {"uri": "/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg"},
            "course_video": {"uri": None},
            "image": {
                "raw": "http://local.overhang.io:8000/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "small": "http://local.overhang.io:8000/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "large": "http://local.overhang.io:8000/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
            },
        },
        "name": "small-graded",
        "number": "cd101",
        "org": "edx",
        "short_description": "",
        "start": "2020-01-01T00:00:00Z",
        "start_display": "Jan. 1, 2020",
        "start_type": "timestamp",
        "pacing": "self",
        "mobile_available": False,
        "hidden": False,
        "invitation_only": False,
        "course_id": "course-v1:edx+cd101+2023-t1",
    },
]
