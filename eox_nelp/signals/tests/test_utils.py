"""This file contains all the test for signals/utils.py file.
Classes:
    UserHasPassingGradeTestCase: Test _user_has_passing_grade function.
    GenerateExternalCertificateDataTestCase: Test _generate_external_certificate_data function.
    CompleteLtiBlockFromAgsScoreTestCase: Test complete_lti_block_from_ags_score function.
"""
import unittest

from custom_reg_form.models import ExtraInfo
from ddt import data, ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx_events.learning.data import CertificateData, CourseData, UserData, UserPersonalData

from eox_nelp.signals.utils import (
    _generate_external_certificate_data,
    _user_has_passing_grade,
    complete_lti_block_from_ags_score,
)

User = get_user_model()

WRONG_NATIONAL_IDS = [0, "", "324234", "VADER", "3666888999", "166688899", "فيدر"]
SAML_EXTRA_ASSOCIATIONS_LIST = ["1666888998ASDF", "1222666444a6ca", "12226664443242344334534543", "1222666444#@$%"]


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


LTI_BLOCK = "block-v1:mcit+aws+T1+type@lti_consumer+block@lesson1"


@patch("eox_nelp.signals.utils.BlockCompletion")
@patch("eox_nelp.signals.utils.get_user_from_external_user_id")
class CompleteLtiBlockFromAgsScoreTestCase(unittest.TestCase):
    """Test class for function `complete_lti_block_from_ags_score`"""

    def _score(self, activity_progress="Completed", score_given=None, resource_link_id=LTI_BLOCK, location=LTI_BLOCK):
        """AGS score stand-in of a line item linked to its own configuration."""
        line_item = Mock(resource_link_id=resource_link_id, lti_configuration=Mock(location=location))

        return Mock(activity_progress=activity_progress, score_given=score_given, line_item=line_item, user_id="sub")

    def test_completes_block(self, get_user_mock, completion_mock):
        """A Completed score without a score writes a full completion of its own block.

        Expected behavior:
            - The user is resolved from the LTI sub.
            - submit_completion is called once with the block UsageKey and 1.0.
            - The outcome is `completed`.
        """
        completion_mock.objects.filter.return_value.exists.return_value = False
        block_key = UsageKey.from_string(LTI_BLOCK)

        outcome = complete_lti_block_from_ags_score(self._score())

        self.assertEqual(outcome, "completed")
        get_user_mock.assert_called_once_with("sub")
        completion_mock.objects.submit_completion.assert_called_once_with(
            user=get_user_mock.return_value, block_key=block_key, completion=1.0,
        )

    def test_dry_run_writes_nothing(self, get_user_mock, completion_mock):  # pylint: disable=unused-argument
        """apply=False reports `completed` without writing."""
        completion_mock.objects.filter.return_value.exists.return_value = False

        outcome = complete_lti_block_from_ags_score(self._score(), apply=False)

        self.assertEqual(outcome, "completed")
        completion_mock.objects.submit_completion.assert_not_called()

    def test_skips(self, get_user_mock, completion_mock):
        """Every early return has its own outcome and never writes.

        Expected behavior:
            - Not Completed, scored, foreign block, unknown user, other user and already complete are skipped.
        """
        completion_mock.objects.filter.return_value.exists.return_value = False
        get_user_mock.return_value = Mock(id=7)
        cases = [
            ("not_completed", self._score(activity_progress="InProgress"), {}),
            ("scored", self._score(score_given=0.8), {}),
            ("out_of_scope", self._score(location="block-v1:mcit+aws+T1+type@lti_consumer+block@other"), {}),
            ("out_of_scope", self._score(resource_link_id=None), {}),
            ("other_user", self._score(), {"only_user_id": 8}),
        ]

        for expected, score, kwargs in cases:
            with self.subTest(expected=expected):
                self.assertEqual(complete_lti_block_from_ags_score(score, **kwargs), expected)

        get_user_mock.return_value = None
        self.assertEqual(complete_lti_block_from_ags_score(self._score()), "unknown_user")

        get_user_mock.return_value = Mock(id=7)
        completion_mock.objects.filter.return_value.exists.return_value = True
        self.assertEqual(complete_lti_block_from_ags_score(self._score(), only_user_id=7), "already_complete")
        completion_mock.objects.submit_completion.assert_not_called()
