"""
Unit tests for programs API v1 utils.
"""

import unittest
from unittest.mock import MagicMock, patch

from eox_nelp.programs.api.v1 import utils


class GetProgramMetadataTestCase(unittest.TestCase):
    """Test cases for get_program_metadata."""

    @patch("eox_nelp.programs.api.v1.utils.modulestore")
    @patch("eox_nelp.programs.api.v1.utils.CourseKey")
    def test_get_program_metadata_found(self, mock_coursekey, mock_modulestore):
        """
        Test retrieving program metadata when present.
        Expected behavior:
            - Returns the program_metadata_v1 dict.
        """
        mock_key = MagicMock()
        mock_coursekey.from_string.return_value = mock_key
        mock_course = MagicMock()
        mock_course.other_course_settings = {"program_metadata_v1": {"foo": "bar"}}
        mock_modulestore.return_value.get_course.return_value = mock_course

        result = utils.get_program_metadata("course-v1:edx+test+2024")

        self.assertEqual(result, {"foo": "bar"})

    @patch("eox_nelp.programs.api.v1.utils.modulestore")
    @patch("eox_nelp.programs.api.v1.utils.CourseKey")
    def test_get_program_metadata_not_found(self, mock_coursekey, mock_modulestore):
        """
        Test retrieving program metadata when not present.
        Expected behavior:
            - Returns empty dict.
        """
        mock_key = MagicMock()
        mock_coursekey.from_string.return_value = mock_key
        mock_course = MagicMock()
        mock_course.other_course_settings = {}
        mock_modulestore.return_value.get_course.return_value = mock_course

        result = utils.get_program_metadata("course-v1:edx+test+2024")

        self.assertEqual(result, {})


class UpdateProgramMetadataTestCase(unittest.TestCase):
    """Test cases for update_program_metadata."""

    @patch("eox_nelp.programs.api.v1.utils.modulestore")
    @patch("eox_nelp.programs.api.v1.utils.CourseKey")
    def test_update_program_metadata(self, mock_coursekey, mock_modulestore):
        """
        Test updating program metadata.
        Expected behavior:
            - Updates the program_metadata_v1 field and calls update_item.
        """
        mock_key = MagicMock()
        mock_coursekey.from_string.return_value = mock_key
        mock_store = MagicMock()
        mock_modulestore.return_value = mock_store
        mock_course = MagicMock()
        mock_course.other_course_settings = {}
        mock_store.get_course.return_value = mock_course
        user = MagicMock(id=123)
        data = {"foo": "bar"}

        utils.update_program_metadata("course-v1:edx+test+2024", data, user)

        self.assertEqual(mock_course.other_course_settings["program_metadata_v1"], data)
        mock_store.update_item.assert_called_once_with(mock_course, user.id)


class GetProgramLookupRepresentationTestCase(unittest.TestCase):
    """Test cases for get_program_lookup_representation."""

    @patch("eox_nelp.programs.api.v1.utils.get_program_metadata")
    @patch("eox_nelp.programs.api.v1.utils.get_user_lms_certificate_path")
    @patch("eox_nelp.programs.api.v1.utils.get_user_generated_certificate")
    def test_get_program_lookup_representation(
        self,
        mock_get_user_generated_certificate,
        mock_get_user_lms_certificate_path,
        mock_get_metadata,
    ):
        """
        Test generating program lookup representation.
        Expected behavior:
            - Returns a dict with all expected fields.
        """
        mock_get_metadata.return_value = {
            "program_code": "CODE",
            "type_of_activity": 1,
            "mandatory": "01",
            "program_approve": "00",
        }
        mock_get_user_generated_certificate.return_value = MagicMock(
            modified_date=MagicMock(strftime=MagicMock(return_value="2024-06-01T00:00:00Z"))
        )
        mock_get_user_lms_certificate_path.return_value = "/certificates/abc-123"
        course_api_data = {
            "course_id": "course-v1:edx+test+2024",
            "name": "Test Course",
            "start": "2020-01-01T00:00:00Z",
            "end": "2020-12-31T00:00:00Z",
            "effort": "5:00",
        }
        user = MagicMock(id=123)
        expected_data = {
            "program_name": "Test Course",
            "program_code": "CODE",
            "training_location": "FutureX",
            "date_start": "2020-01-01",
            "date_start_hijri": "1441-05-06",
            "date_end": "2020-12-31",
            "date_end_hijri": "1442-05-16",
            "trainer_type": 10,
            "type_of_activity": None,
            "type_of_activity_id": 1,
            "unit": "hour",
            "duration": 5,
            "mandatory": "01",
            "program_approve": "00",
            "code": "course-v1:edx+test+2024",
            "certificate_path": "/certificates/abc-123",
            "completion_date": "2024-06-01",
            "completion_date_hijri": "1445-11-24",
        }

        result = utils.get_program_lookup_representation(user, course_api_data)

        self.assertDictEqual(result, expected_data)


class ConvertToIsoformatTestCase(unittest.TestCase):
    """Test cases for convert_to_isoformat."""

    def test_convert_to_isoformat_valid(self):
        """
        Test parsing a valid UTC datetime string.
        Expected behavior:
            - Returns ISO date string.
        """
        self.assertEqual(utils.convert_to_isoformat("2023-01-01T12:00:00Z"), "2023-01-01")

    def test_convert_to_isoformat_none(self):
        """
        Test parsing None input.
        Expected behavior:
            - Returns None.
        """
        self.assertIsNone(utils.convert_to_isoformat(None))

    def test_convert_to_isoformat_invalid(self):
        """
        Test parsing an invalid date string.
        Expected behavior:
            - Returns None and logs error.
        """
        with self.assertLogs(utils.logger, level="ERROR"):
            self.assertIsNone(utils.convert_to_isoformat("not-a-date"))


class HmsToIntTestCase(unittest.TestCase):
    """Test cases for hms_to_int."""

    def test_hms_to_int_hhmm(self):
        """
        Test converting "HH:MM" format.
        Expected behavior:
            - Returns rounded integer hours.
        """
        self.assertEqual(utils.hms_to_int("2:31"), 3)
        self.assertEqual(utils.hms_to_int("1:29"), 1)
        self.assertEqual(utils.hms_to_int("0:45"), 1)

    def test_hms_to_int_hh(self):
        """
        Test converting "HH" format.
        Expected behavior:
            - Returns integer hours.
        """
        self.assertEqual(utils.hms_to_int("5"), 5)
        self.assertEqual(utils.hms_to_int("0"), 0)

    def test_hms_to_int_invalid(self):
        """
        Test invalid input.
        Expected behavior:
            - Returns None and logs warning.
        """
        with self.assertLogs(utils.logger, level="WARNING"):
            self.assertIsNone(utils.hms_to_int("bad"))
            self.assertIsNone(utils.hms_to_int("2:bad"))

    def test_hms_to_int_none(self):
        """
        Test None input.
        Expected behavior:
            - Returns None.
        """
        self.assertIsNone(utils.hms_to_int(None))

    def test_hms_to_int_minutes_out_of_range(self):
        """
        Test minutes out of range in "HH:MM".
        Expected behavior:
            - Treats invalid minutes as 0.
        """
        self.assertEqual(utils.hms_to_int("2:99"), 2)
        self.assertEqual(utils.hms_to_int("2:-5"), 2)

    class GetUserLmsCertificatePathTestCase(unittest.TestCase):
        """Test cases for get_user_lms_certificate_path."""

        @patch("eox_nelp.programs.api.v1.utils.certificates_utils._certificate_html_url")
        @patch("eox_nelp.programs.api.v1.utils.certificates_utils.certificate_status_for_student")
        def test_returns_certificate_path(self, mock_cert_status, mock_cert_url):
            """
            Test that the function returns the correct certificate path.
            Expected behavior:
                - Returns the LMS certificate path for the user and course.
                - Calls certificate_status_for_student and _certificate_html_url with correct parameters.
            """
            generated_certificate = MagicMock()
            mock_cert_status.return_value = {"uuid": "abc-123"}
            mock_cert_url.return_value = "/certificates/abc-123"

            result = utils.get_user_lms_certificate_path(generated_certificate)

            mock_cert_status.assert_called_once_with(generated_certificate)
            mock_cert_url.assert_called_once_with(uuid="abc-123")
            self.assertEqual(result, "/certificates/abc-123")
