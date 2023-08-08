"""This file contains all the test for signals/utils.py file.
Classes:
    UserHasPassingGradeTestCase: Test _user_has_passing_grade function.
    GenerateExternalCertificateDataTestCase: Test _generate_external_certificate_data function.
"""
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey
from openedx_events.learning.data import CertificateData, CourseData, UserData, UserPersonalData

from eox_nelp.signals.utils import _generate_external_certificate_data, _user_has_passing_grade

User = get_user_model()


class UserHasPassingGradeTestCase(unittest.TestCase):
    """Test class for function `_user_has_passing_grade`"""

    @patch("eox_nelp.signals.utils.CourseGradeFactory")
    def test_call_user_has_passing_grade(self, course_grade_factory_mock):
        """Test when `_user_has_passing_grade` is called
        with the required parameters. Check the functions inside are called with
        their desired values.

        Expected behavior:
            - CourseGradeFactory class is used with the right values.
        """
        user, _ = User.objects.get_or_create(username="vader")
        course_id = "course-v1:test+Cx105+2022_T4"

        _user_has_passing_grade(user, course_id)
        course_grade_factory_mock().read.assert_called_with(user, course_key=CourseKey.from_string(course_id))


class GenerateExternalCertificateDataTestCase(unittest.TestCase):
    """Test class for function `_generate_external_certificate_data`"""

    def setUp(self):
        """ Set common conditions for test cases."""
        self.user, _ = User.objects.get_or_create(
            username="10024578",
        )
        self.certificate_data = CertificateData(
            user=UserData(
                pii=UserPersonalData(
                    username=self.user.username,
                    email="harry@potter.com",
                    name="Harry Potter",
                ),
                id=self.user.id,
                is_active=True,
            ),
            course=CourseData(
                course_key=CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            ),
            mode="audit",
            grade=15,
            current_status="non-passing",
            download_url="",
            name="",
        )

    @override_settings(EXTERNAL_CERTIFICATES_GROUP_CODES={"course-v1:test+Cx105+2022_T4": "ABC123"})
    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    @patch("eox_nelp.signals.utils.GeneratedCertificate")
    def test_generate_certificate_data(self, generate_certificate_mock, passing_mock):
        """This tests the normal behavior of the method `_generate_external_certificate_data`

        Expected behavior:
            - Result is as the expected value
            - GeneratedCertificate mock is called with the right parameters.
            - _user_has_passing_grade is called with the right parameters.
        """
        time = timezone.now()
        certificate = Mock()
        certificate.id = 85
        generate_certificate_mock.objects.get.return_value = certificate
        passing_mock.return_value = True

        expected_value = {
            "id": certificate.id,
            "created_at": time,
            "expiration_date": time + timezone.timedelta(days=365),
            "grade": self.certificate_data.grade,
            "is_passing": True,
            "group_code": settings.EXTERNAL_CERTIFICATES_GROUP_CODES[str(self.certificate_data.course.course_key)],
            "user": {
                "national_id": self.user.username,
                "english_name": self.certificate_data.user.pii.name,
                "arabic_name": "",
            }
        }

        result = _generate_external_certificate_data(time, self.certificate_data)

        self.assertEqual(result, expected_value)
        generate_certificate_mock.objects.get.assert_called_once_with(
            user=self.user,
            course_id=self.certificate_data.course.course_key,
        )
        passing_mock.assert_called_once_with(
            self.user,
            str(self.certificate_data.course.course_key)
        )

    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    @patch("eox_nelp.signals.utils.GeneratedCertificate")
    def test_invalid_group_codes(self, generate_certificate_mock, passing_mock):
        """This tests when the EXTERNAL_CERTIFICATES_GROUP_CODES value has not been set.

        Expected behavior:
            - Raise KeyError
        """
        certificate = Mock()
        certificate.id = 85
        generate_certificate_mock.objects.get.return_value = certificate
        passing_mock.return_value = True
        data = {
            "timestamp": timezone.now(),
            "certificate_data": self.certificate_data,
        }

        self.assertRaises(KeyError, _generate_external_certificate_data, **data)
