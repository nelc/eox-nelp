"""This file contains all the test for signals/utils.py file.
Classes:
    UserHasPassingGradeTestCase: Test _user_has_passing_grade function.
    GenerateExternalCertificateDataTestCase: Test _generate_external_certificate_data function.
"""
import unittest

import pytest
from custom_reg_form.models import ExtraInfo
from ddt import data, ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from mock import patch
from opaque_keys.edx.keys import CourseKey
from openedx_events.learning.data import CertificateData, CourseData, UserData, UserPersonalData

from eox_nelp.signals.utils import _generate_external_certificate_data, _user_has_passing_grade

User = get_user_model()

WRONG_NATIONAL_IDS = [0, "", "324234", "VADER", "3666888999", "166688899", "فيدر"]
SAML_EXTRA_ASSOCIATIONS_LIST = ["1666888998ASDF", "1222666444a6ca", "12226664443242344334534543", "1222666444#@$%"]


@pytest.mark.django_db
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


@ddt
class GenerateExternalCertificateDataTestCase(TestCase):
    """Test class for function `_generate_external_certificate_data`"""

    def setUp(self):
        """ Set common conditions for test cases."""
        self.user, _ = User.objects.get_or_create(
            username="RonWeasley",
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
            grade=0.85,
            current_status="non-passing",
            download_url="",
            name="",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=self.user,
            arabic_name="مسؤل",
            national_id="1234567890",
        )

    @override_settings(EXTERNAL_CERTIFICATES_GROUP_CODES={"course-v1:test+Cx105+2022_T4": "ABC123"})
    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    def test_generate_certificate_data(self, passing_mock):
        """This tests the normal behavior of the method `_generate_external_certificate_data`

        Expected behavior:
            - Result is as the expected value
            - GeneratedCertificate mock is called with the right parameters.
            - _user_has_passing_grade is called with the right parameters.
        """
        time = timezone.now()
        passing_mock.return_value = True

        expected_value = {
            'reference_id': f'{self.user.extrainfo.national_id}~course-v1:test+Cx105+2022_T4',
            "created_at": str(time.date()),
            "expiration": None,
            "grade": self.certificate_data.grade * 100,
            "is_passing": True,
            "group_code": settings.EXTERNAL_CERTIFICATES_GROUP_CODES[str(self.certificate_data.course.course_key)],
            "user": {
                "national_id": self.user.extrainfo.national_id,
                "english_name": self.certificate_data.user.pii.name,
                "arabic_name": "مسؤل",
            }
        }

        result = _generate_external_certificate_data(time, self.certificate_data)

        self.assertEqual(result, expected_value)
        passing_mock.assert_called_once_with(
            self.user,
            str(self.certificate_data.course.course_key)
        )

    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    def test_invalid_group_codes(self, passing_mock):
        """This tests when the EXTERNAL_CERTIFICATES_GROUP_CODES value has not been set.

        Expected behavior:
            - Raise KeyError
        """
        passing_mock.return_value = True
        external_certificate_data = {
            "time": timezone.now(),
            "certificate_data": self.certificate_data,
        }

        self.assertRaises(KeyError, _generate_external_certificate_data, **external_certificate_data)

    @override_settings(EXTERNAL_CERTIFICATES_GROUP_CODES={"course-v1:test+Cx105+2022_T4": "ABC123"})
    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    @data(*WRONG_NATIONAL_IDS)
    def test_invalid_national_id(self, wrong_national_id, passing_mock):
        """This tests when the user has an invalid NationalId.

        Expected behavior:
            - Raise ValueError
        """
        passing_mock.return_value = True
        wrong_user, _ = User.objects.get_or_create(
            username="Albus",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=wrong_user,
            arabic_name="مسؤل",
            national_id=wrong_national_id,
        )
        certificate_data = CertificateData(
            user=UserData(
                pii=UserPersonalData(
                    username=wrong_user.username,
                    email="harry@potter.com",
                    name="Harry Potter",
                ),
                id=wrong_user.id,
                is_active=True,
            ),
            course=CourseData(
                course_key=CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            ),
            mode="audit",
            grade=0.85,
            current_status="non-passing",
            download_url="",
            name="",
        )
        external_certificate_data = {
            "time": timezone.now(),
            "certificate_data": certificate_data,
        }

        self.assertRaisesRegex(
            ValueError,
            f"The username or national_id: {wrong_user.extrainfo.national_id} doesnt match national ID regex",
            _generate_external_certificate_data,
            **external_certificate_data,
        )

    @override_settings(EXTERNAL_CERTIFICATES_GROUP_CODES={"course-v1:test+Cx105+2022_T4": "ABC123"})
    @patch("eox_nelp.signals.utils._user_has_passing_grade")
    @data(*SAML_EXTRA_ASSOCIATIONS_LIST)
    def test_generate_certificate_data_saml_extra_association(
        self,
        saml_extra_association,
        passing_mock
    ):
        """This tests the normal behavior ofa user with saml_extra_association
        the method `_generate_external_certificate_data`

        Expected behavior:
            - Result is as the expected value
            - GeneratedCertificate mock is called with the right parameters.
            - _user_has_passing_grade is called with the right parameters.
        """
        time = timezone.now()
        passing_mock.return_value = True
        saml_association_user, _ = User.objects.get_or_create(
            username="Severus",
        )
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=saml_association_user,
            arabic_name="مسؤل",
            national_id=saml_extra_association,
        )
        certificate_data = CertificateData(
            user=UserData(
                pii=UserPersonalData(
                    username=saml_association_user.username,
                    email="harry@potter.com",
                    name="Harry Potter",
                ),
                id=saml_association_user.id,
                is_active=True,
            ),
            course=CourseData(
                course_key=CourseKey.from_string("course-v1:test+Cx105+2022_T4"),
            ),
            mode="audit",
            grade=0.88,
            current_status="non-passing",
            download_url="",
            name="",
        )
        national_id = saml_association_user.extrainfo.national_id[:10]

        expected_value = {
            'reference_id': f'{national_id}~course-v1:test+Cx105+2022_T4',
            "created_at": str(time.date()),
            "expiration": None,
            "grade": certificate_data.grade * 100,
            "is_passing": True,
            "group_code": settings.EXTERNAL_CERTIFICATES_GROUP_CODES[str(self.certificate_data.course.course_key)],
            "user": {
                "national_id": national_id,
                "english_name": certificate_data.user.pii.name,
                "arabic_name": "مسؤل",
            }
        }

        result = _generate_external_certificate_data(time, certificate_data)

        self.assertEqual(result, expected_value)
        passing_mock.assert_called_once_with(
            saml_association_user,
            str(certificate_data.course.course_key)
        )
