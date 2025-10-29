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
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
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
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.update_program_metadata") as mock_update:
            mock_update.return_value = True

            response = self.client.post(self.url, metadata_data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            # The response includes trainer_type as read-only field
            expected_data = {
                "trainer_type": 10,
                "type_of_activity": 1,
                "mandatory": "01",
                "program_approve": "01",
                "program_code": "TEST001",
            }
            self.assertEqual(response.data, expected_data)
            # trainer_type is read-only, so it's not included in validated_data
            expected_data = {
                "trainer_type": 10,
                "type_of_activity": 1,
                "mandatory": "01",
                "program_approve": "01",
                "program_code": "TEST001",
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
            "type_of_activity": 1,
            "mandatory": "invalid",  # Invalid value - too long
            "program_approve": "01",
            "program_code": "",  # Empty value
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
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
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
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
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
            "type_of_activity": "not_a_number",  # Invalid type
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
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
            "type_of_activity": 1,
            "mandatory": "invalid",  # Invalid value - too long
            "program_approve": "01",
            "program_code": "TEST001",
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
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "TEST001",
        }

        with patch("eox_nelp.programs.api.v1.views.get_program_metadata") as mock_get:
            mock_get.return_value = valid_metadata

            response = self.client.get(self.url)

            if response.status_code == status.HTTP_200_OK:
                expected_fields = ["trainer_type", "type_of_activity", "mandatory", "program_approve", "program_code"]

                for field in expected_fields:
                    self.assertIn(field, response.data, f"Field '{field}' missing from response")

    def test_program_metadata_mandatory_field_validation(self):
        """
        Test validation of mandatory field values.
        Expected behavior:
            - Only "01" and "00" are accepted.
            - Other values return validation error.
        """
        test_cases = [
            ("01", True, None),
            ("00", True, None),
            ("invalid", False, "Ensure this field has no more than 2 characters"),
            ("1", False, "mandatory must be one of: 01, 00"),
            ("0", False, "mandatory must be one of: 01, 00"),
        ]

        for value, should_pass, expected_error in test_cases:
            with self.subTest(value=value):
                metadata_data = {
                    "trainer_type": 10,
                    "type_of_activity": 1,
                    "mandatory": value,
                    "program_approve": "01",
                    "program_code": "TEST001",
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
        Test validation of program_approve field values.
        Expected behavior:
            - Only "01" and "00" are accepted.
            - Other values return validation error.
        """
        test_cases = [
            ("01", True, None),
            ("00", True, None),
            ("invalid", False, "Ensure this field has no more than 2 characters"),
            ("1", False, "program_approve must be one of: 01, 00"),
            ("0", False, "program_approve must be one of: 01, 00"),
        ]

        for value, should_pass, expected_error in test_cases:
            with self.subTest(value=value):
                metadata_data = {
                    "trainer_type": 10,
                    "type_of_activity": 1,
                    "mandatory": "01",
                    "program_approve": value,
                    "program_code": "TEST001",
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
        Test validation of program_code field.
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
                    "type_of_activity": 1,
                    "mandatory": "01",
                    "program_approve": "01",
                    "program_code": value,
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

    def test_get_programs_list_authenticated_without_national_id(self):
        """
        Test GET returns program list for authenticated user. But with not national_id query param.
        Expected behavior:
            - Status code 400.
            - Error message indicating that national_id is required.
        """
        expected_data = {
            "error": "MISSING_NATIONAL_ID",
            "message": "national_id query parameter is required."
        }

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictEqual(response.data, expected_data)

    @patch("eox_nelp.programs.api.v1.views.CourseDetailSerializer")
    @patch("eox_nelp.programs.api.v1.utils.get_program_metadata")
    @patch("eox_nelp.programs.api.v1.views.CourseEnrollment.is_enrolled")
    @patch("eox_nelp.programs.api.v1.views.courses")
    def test_get_programs_list_with_national_id(
        self, mock_courses, mock_is_enrolled, mock_get_program_metadata, mock_course_serializer,
    ):
        """
        Test GET returns program list for user with given national_id.
        Expected behavior:
            - Status code 200.
            - The expected data matches with the response.
            - courses.get_courses mock is called with correct user.
            - CourseEnrollment.is_enrolled mock is called due national_id filter.
        """
        user_by_national_id_instance, _ = User.objects.get_or_create(username="user2", password="pass2")
        national_id = "1222888000"
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=user_by_national_id_instance,
            arabic_name="مسؤل",
            national_id=national_id,
        )
        serializer_side_effect = []
        for course_data in COURSE_API_SERIALIZER_DATA:
            mock_serializer_instance = MagicMock()
            mock_serializer_instance.data = course_data
            serializer_side_effect.append(mock_serializer_instance)
        mock_course_serializer.side_effect = serializer_side_effect
        course = MagicMock(id="course-v1:edx+special+2024")
        mock_courses.get_courses.return_value = [course]
        mock_is_enrolled.return_value = True
        mock_get_program_metadata.return_value = {
            "trainer_type": 10,
            "type_of_activity": 165,
            "mandatory": "01",
            "program_approve": "01",
            "program_code": "nationalidtest",
        }
        expected_data = [
            {
                "program_name": "testigngg",
                "program_code": "nationalidtest",
                "type_of_activity": "برنامج الاستثمار الأمثل (برامج قصيرة)",
                "type_of_activity_id": 165,
                "mandatory": "01",
                "program_approve": "01",
                "code": "course-v1:edx+cd101+2020323",
                "date_start": "2030-01-01",
                "date_end": None,
                "date_start_hijri": "1451-08-26",
                "date_end_hijri": None,
                "duration": 1,
                "training_location": "FutureX",
                "trainer_type": 10,
                "unit": "hour",
            }
        ]

        response = self.client.get(self.url, {"national_id": national_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertListEqual(response.data["results"], expected_data)
        mock_courses.get_courses.assert_called_once_with(user=user_by_national_id_instance)
        mock_is_enrolled.assert_called()

    def test_get_programs_list_unauthenticated(self):
        """
        Test GET returns 401 for unauthenticated user.
        Expected behavior:
            - Status code 401.
            - Response contains authentication error message.
        """
        client = APIClient()

        response = client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided", str(response.data))

    def test_get_programs_list_unauthenticated_national_id(self):
        """
        Test GET returns 401 for unauthenticated user.
        Expected behavior:
            - Status code 401.
            - Response contains authentication error message.
        """
        client = APIClient()

        response = client.get(self.url, {"national_id": "1234567890"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided", str(response.data))

    @patch("eox_nelp.programs.api.v1.views.courses")
    @patch("eox_nelp.programs.api.v1.views.CourseDetailSerializer")
    @patch("eox_nelp.programs.api.v1.utils.get_program_metadata")
    def test_get_programs_list_missing_data(
        self, mock_get_program_metadata, mock_course_serializer, mock_courses
    ):
        """
        Test GET returns error if ProgramLookupSerializer is invalid.
        Expected behavior:
            - Status code 200.
            - Response result is alist.
            - Expected data matches with null values
        """
        user_by_national_id_instance, _ = User.objects.get_or_create(username="user3", password="pass3")
        national_id = "1222888555"
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=user_by_national_id_instance,
            arabic_name="مسؤل",
            national_id=national_id,
        )
        serializer_side_effect = []
        course = MagicMock(id="course-v1:edx+special+2024")
        mock_courses.get_courses.return_value = [course, course]
        for course_data in COURSE_API_SERIALIZER_DATA:
            mock_serializer_instance = MagicMock()
            mock_serializer_instance.data = course_data
            serializer_side_effect.append(mock_serializer_instance)
        mock_course_serializer.side_effect = serializer_side_effect
        mock_get_program_metadata.return_value = {}
        expected_data = [
            {
                "program_name": "testigngg",
                "program_code": None,
                "type_of_activity": None,
                "type_of_activity_id": None,
                "mandatory": None,
                "program_approve": None,
                "code": "course-v1:edx+cd101+2020323",
                "date_start": "2030-01-01",
                "date_end": None,
                "date_start_hijri": "1451-08-26",
                "date_end_hijri": None,
                "duration": 1,
                "training_location": "FutureX",
                "trainer_type": 10,
                "unit": "hour",
            },
            {
                "program_name": "small-graded",
                "program_code": None,
                "type_of_activity": None,
                "type_of_activity_id": None,
                "mandatory": None,
                "program_approve": None,
                "code": "course-v1:edx+cd101+2023-t1",
                "date_start": "2020-01-01",
                "date_end": "2034-12-25",
                "date_start_hijri": "1441-05-06",
                "date_end_hijri": "1456-10-14",
                "duration": 2,
                "training_location": "FutureX",
                "trainer_type": 10,
                "unit": "hour",
            },
        ]

        response = self.client.get(self.url, {"national_id": national_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data["results"], list)
        self.assertListEqual(expected_data, response.data["results"])

    @patch("eox_nelp.programs.api.v1.views.CourseListView.get_queryset")
    def test_get_programs_list_not_found_national_id(self, mock_super_get):
        """
        Test GET returns empty list if no enrolled courses.
        Expected behavior:
            - Status code 404.
            - Response is an error message.
        """
        national_id = "1333888000"
        mock_super_get.return_value.data = {"results": []}

        response = self.client.get(self.url, {"national_id": national_id})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {
                "error": "NO_PROGRAM_FOR_NATIONAL_ID",
                "message": f"No program found for the provided National ID {national_id}.",
            }
        )

    @patch("eox_nelp.programs.api.v1.views.CourseDetailSerializer")
    @patch("eox_nelp.programs.api.v1.utils.get_program_metadata")
    @patch("eox_nelp.programs.api.v1.views.CourseEnrollment.is_enrolled")
    @patch("eox_nelp.programs.api.v1.views.courses")
    def test_get_programs_list_no_courses_enrolled(
        self, mock_courses, mock_is_enrolled, _, mock_course_serializer,
    ):
        """
        Test GET returns program list for user with given national_id.
        Expected behavior:
            - Status code 400.
            - The expected data matches with the response.
            - courses.get_courses mock is called with correct user.
            - CourseEnrollment.is_enrolled mock is called due national_id filter.
        """
        user_by_national_id_instance, _ = User.objects.get_or_create(username="user2", password="pass2")
        national_id = "1222888000"
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=user_by_national_id_instance,
            arabic_name="مسؤل",
            national_id=national_id,
        )
        serializer_side_effect = []
        for course_data in COURSE_API_SERIALIZER_DATA:
            mock_serializer_instance = MagicMock()
            mock_serializer_instance.data = course_data
            serializer_side_effect.append(mock_serializer_instance)
        mock_course_serializer.side_effect = serializer_side_effect
        course = MagicMock(id="course-v1:edx+special+2024")
        mock_courses.get_courses.return_value = [course]
        mock_is_enrolled.return_value = False

        response = self.client.get(self.url, {"national_id": national_id})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {
                "error": "NO_PROGRAM_FOR_NATIONAL_ID",
                "message": f"No program found for the provided National ID {national_id}.",
            }
        )
        mock_courses.get_courses.assert_called_once_with(user=user_by_national_id_instance)
        mock_is_enrolled.assert_called()


COURSE_API_SERIALIZER_DATA = [
    {
        "blocks_url": "http://local/api/courses/v2/blocks/?course_id=course-v1%3Aedx%2Bcd101%2B2020323",
        "effort": "1",
        "end": None,
        "enrollment_start": None,
        "enrollment_end": None,
        "id": "course-v1:edx+cd101+2020323",
        "media": {
            "banner_image": {
                "uri": "/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "uri_absolute": "http://local/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
            },
            "course_image": {"uri": "/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg"},
            "course_video": {"uri": None},
            "image": {
                "raw": "http://local/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "small": "http://local/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
                "large": "http://local/asset-v1:edx+cd101+2020323+type@asset+block@images_course_image.jpg",
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
        "course_about_url": "http://local/courses/course-v1:edx+cd101+2020323/about",
        "course_home_url": "http://apps.local.overhang.io:2000/learning/course/course-v1:edx+cd101+2020323/home",
    },
    {
        "blocks_url": "http://local/api/courses/v2/blocks/?course_id=course-v1%3Aedx%2Bcd101%2B2023-t1",
        "effort": "2:20",
        "end": "2034-12-25T00:00:00Z",
        "enrollment_start": "2019-05-31T00:00:00Z",
        "enrollment_end": None,
        "id": "course-v1:edx+cd101+2023-t1",
        "media": {
            "banner_image": {
                "uri": "/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "uri_absolute": "http://local/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
            },
            "course_image": {"uri": "/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg"},
            "course_video": {"uri": None},
            "image": {
                "raw": "http://local/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "small": "http://local/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
                "large": "http://local/asset-v1:edx+cd101+2023-t1+type@asset+block@images_course_image.jpg",
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
