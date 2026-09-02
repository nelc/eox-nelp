# pylint: disable=too-many-lines
"""This file contains all the test for tasks.py file.

Classes:
    GetCompletionSummaryTestCase: Test get_completion_summary method.
    GenerateProgressEnrollmentDataTestCase: Test _generate_progress_enrollment_data method.
    UpdateMtTrainingStageTestCase: Test update_mt_training_stage task.
    CourseCompletionMtUpdaterTestCase: Test course_completion_mt_updater task.
"""
import unittest
from datetime import timedelta

from custom_reg_form.models import ExtraInfo
from ddt import data, ddt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from mock import Mock, patch
from opaque_keys.edx.keys import CourseKey, UsageKey
from social_django.models import UserSocialAuth

from eox_nelp.edxapp_wrapper.course_blocks import get_student_module_as_dict
from eox_nelp.edxapp_wrapper.course_modes import CourseMode
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview
from eox_nelp.edxapp_wrapper.grades import SubsectionGradeFactory
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.mt.models import MTTrainingStageDelivery
from eox_nelp.signals import tasks
from eox_nelp.signals.exceptions import MTTrainingStageError
from eox_nelp.signals.tasks import (
    _generate_progress_enrollment_data,
    _post_futurex_progress,
    course_completion_mt_updater,
    create_course_mode,
    dispatch_futurex_progress,
    emit_subsection_attempt_event_task,
    reconcile_mt_training_stages,
    set_default_advanced_modules,
    update_mt_training_stage,
)
from eox_nelp.signals.utils import get_completion_summary
from eox_nelp.tests.utils import generate_list_mock_data

User = get_user_model()
FALSY_ACTIVATION_VALUES = [0, "", None, [], False, {}, ()]
TRUTHY_ACTIVATION_VALUES = [1, "true", "activated", ["activated"], True, {"activated": "true"}]


@ddt
class DipatchFuturexProgressTestCase(unittest.TestCase):
    """Test class for function `dispatch_futurex_progress`"""

    @override_settings()
    @patch("eox_nelp.signals.tasks._generate_progress_enrollment_data")
    @patch("eox_nelp.signals.tasks._post_futurex_progress")
    @data(*TRUTHY_ACTIVATION_VALUES)
    def test_call_dispatch_futurex_progress(
        self, truthy_value, post_futurex_progress_mock, generate_progress_enrollment_data_mock,
    ):
        """Test when `dispatch_futurex_progress` is called
        with the required parameters. Check the functions inside are called with
        their desired values. Also with the setting `ACTIVATE_DISPATCH_FUTUREX_PROGRESS` configurated
        with truthy value.

        Expected behavior:
            - `_generate_progress_enrollment_data` is called with the right values.
            - `post_futurex_progress` is called with the right values.
        """
        user, _ = User.objects.get_or_create(username="vader")
        course_id = "course-v1:test+Cx105+2022_T4"
        progress_enrollment_data = {
            "courseId": "course-v1:edX+213+2121",
            "userId": 16734,
            "approxTotalCourseHrs": None,
            "overallProgress": 0.16279069767441862,
            "membershipState": True,
            "enrolledAt": "2023-03-16T20:24:19.494709Z",
            "isCompleted": False,
        }
        generate_progress_enrollment_data_mock.return_value = progress_enrollment_data
        setattr(settings, "ACTIVATE_DISPATCH_FUTUREX_PROGRESS", truthy_value)

        dispatch_futurex_progress(course_id, user.id, is_complete=True)

        generate_progress_enrollment_data_mock.assert_called_with(
            user=user,
            course_id=course_id,
            user_has_passing_grade=True,
        )
        post_futurex_progress_mock.assert_called_with(progress_enrollment_data)

    @override_settings()
    @patch("eox_nelp.signals.tasks._generate_progress_enrollment_data")
    @patch("eox_nelp.signals.tasks._post_futurex_progress")
    def test_not_call_dispatch_logic_setting_not_configured(
        self, post_futurex_progress_mock, generate_progress_enrollment_data_mock
    ):
        """Test `dispatch_futurex_progress` is called but the logic inside not.
        So `generate_progress_enrollment_data` and `post_futurex_progress` are not called
        due no setting configured.

        Expected behavior:
            - generate_progress_enrollment_data is not called due settings.
            - post_futurex_progress_mock is not called due settings.
        """
        user, _ = User.objects.get_or_create(username="vader")
        course_id = "course-v1:test+Cx105+2022_T4"
        if hasattr(settings, "ACTIVATE_DISPATCH_FUTUREX_PROGRESS"):
            delattr(settings, "ACTIVATE_DISPATCH_FUTUREX_PROGRESS")

        dispatch_futurex_progress(course_id, user.id, is_complete=True)

        generate_progress_enrollment_data_mock.assert_not_called()
        post_futurex_progress_mock.assert_not_called()

    @override_settings()
    @patch("eox_nelp.signals.tasks._generate_progress_enrollment_data")
    @patch("eox_nelp.signals.tasks._post_futurex_progress")
    @data(*FALSY_ACTIVATION_VALUES)
    def test_not_call_dispatch_logic_setting_falsy(
        self, falsy_value, post_futurex_progress_mock, generate_progress_enrollment_data_mock,
    ):
        """Test `dispatch_futurex_progress` is called but the logic inside not.
        So `generate_progress_enrollment_data` and `post_futurex_progress` are not called
        due setting configured with falsy value.

        Expected behavior:
            - generate_progress_enrollment_data is not called due settings.
            - post_futurex_progress_mock is not called due settings.
        """
        user, _ = User.objects.get_or_create(username="vader")
        course_id = "course-v1:test+Cx105+2022_T4"
        setattr(settings, "ACTIVATE_DISPATCH_FUTUREX_PROGRESS", falsy_value)

        dispatch_futurex_progress(course_id, user.id, is_complete=True)

        generate_progress_enrollment_data_mock.assert_not_called()
        post_futurex_progress_mock.assert_not_called()


class PostFuturexProgressTestCase(unittest.TestCase):
    """Test class for function `_post_futurex_progress`"""

    @patch("eox_nelp.signals.tasks.FuturexApiClient")
    @override_settings(
        FUTUREX_CLIENT_ID="test-client-id",
        FUTUREX_CLIENT_SECRET="test-client-secret",
        FUTUREX_TOKEN_URL="test-token-url",
        FUTUREX_API_BASE_URL="test-api-base-url",
    )
    def test_dispatch_futurex_progress(self, futurex_api_client_mock):
        """Test when `_post_futurex_progress` is called
        with the required parameters. Check the functions inside are called with
        their desired values.

        Expected behavior:
            - FuturexApiClient is used with the right values.
            - Log successful sent to service message.
        """
        progress_enrollment_data = {
            "courseId": "course-v1:edX+213+2121",
            "userId": 16734,
            "approxTotalCourseHrs": None,
            "overallProgress": 0.16279069767441862,
            "membershipState": True,
            "enrolledAt": "2023-03-16T20:24:19.494709Z",
            "isCompleted": False,
        }
        service_base_url = "testingfuturexsink.com"
        service_response = {'status': {'success': True, 'message': 'successful', 'code': 1}}
        log_post = (
            f"send_futurex_progress --- "
            f"The data {progress_enrollment_data} was sent to the futurex service host {service_base_url}. "
            f"The response was: {service_response}"
        )
        futurex_api_client_mock().base_url = service_base_url
        futurex_api_client_mock().send_enrollment_progress.return_value = service_response

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            _post_futurex_progress(progress_enrollment_data)

        futurex_api_client_mock().send_enrollment_progress.assert_called_with(progress_enrollment_data)
        self.assertEqual(logs.output, [f"INFO:{tasks.__name__}:{log_post}"])


class GetCompletionSummaryTestCase(unittest.TestCase):
    """Test class for get_completion_summary"""

    @patch("eox_nelp.signals.utils.courses")
    def test_get_course_blocks(self, courses_mock):
        """Test standard call with the required parameters.

        Expected behavior:
            - get_course_blocks_completion_summary is called with the right values.
        """
        user, _ = User.objects.get_or_create(username="Salazar")
        course_id = "course-v1:test+Cx105+2022_T4"
        course_key = CourseKey.from_string(course_id)

        get_completion_summary(user, course_id)

        courses_mock.get_course_blocks_completion_summary.assert_called_with(course_key, user)


class GenerateProgressEnrollmentDataTestCase(unittest.TestCase):
    """Test class for _generate_progress_enrollment_data."""

    def setUp(self):
        """ Set common conditions for test cases."""
        patcher1 = patch("eox_nelp.signals.tasks.get_completion_summary")
        patcher2 = patch("eox_nelp.signals.tasks.get_enrollment")
        patcher3 = patch("eox_nelp.signals.tasks.CourseOverview")

        self.completion_summary_mock = patcher1.start()
        self.enrollment_mock = patcher2.start()
        self.course_overview_mock = patcher3.start()

        self.lms_user, _ = User.objects.get_or_create(username="Godric")

        self.saml_user, _ = User.objects.get_or_create(username="Salazar")
        self.saml_social_user, _ = UserSocialAuth.objects.get_or_create(
            user=self.saml_user,
            provider="tpa-saml",
            extra_data={"uid": 1313}
        )
        UserSocialAuth.objects.get_or_create(
            user=self.saml_user,
            provider="tpa-saml",
        )
        UserSocialAuth.objects.get_or_create(
            user=self.saml_user,
            provider="okta",
        )

        self.patchers = [patcher1, patcher2, patcher3]

    def tearDown(self):
        """Stop patching."""
        for patcher in self.patchers:
            patcher.stop()

    def test_empty_completion_summary(self):
        """Test when get_completion_summary returns an empty list.

        Expected behavior:
            - completion_summary is called with the right values.
            - get_enrollment is called with the right values.
            - Log successful message.
            - Returned data is as expected.
        """
        self.completion_summary_mock.return_value = []
        self.enrollment_mock.return_value = (
            {
                "is_active": True,
                "created": "2022-11-01T22:05:47.082806Z"
            },
            None,
        )
        self.course_overview_mock.objects.get.return_value.effort = 10
        course_id = "course-v1:test+Cx105+2022_T4"
        expected_data = {
            "courseId": course_id,
            "userId": self.saml_social_user.extra_data["uid"],
            "approxTotalCourseHrs": 10,
            "overallProgress": None,
            "membershipState": True,
            "enrolledAt": "2022-11-01T22:05:47.082806Z",
            "isCompleted": False,
        }
        log_error = f"send_futurex_progress --- Successful extraction of progress_enrollment_data: {expected_data}"

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            progress_data = _generate_progress_enrollment_data(self.saml_user, course_id, False)

        self.completion_summary_mock.assert_called_with(self.saml_user, course_id)
        self.enrollment_mock.assert_called_with(username=self.saml_user.username, course_id=course_id)
        self.assertEqual(logs.output, [
            f"INFO:{tasks.__name__}:{log_error}"
        ])
        self.assertDictEqual(expected_data, progress_data)

    def test_populated_completion_summary(self):
        """Test when get_completion_summary returns a dictionary with the standard data.

        Expected behavior:
            - completion_summary is called with the right values.
            - get_enrollment is called with the right values.
            - Log successful message.
            - Returned data is as expected.
        """
        self.completion_summary_mock.return_value = {
            "complete_count": 15,
            "incomplete_count": 60,
            "locked_count": 5
        }
        self.enrollment_mock.return_value = (
            {
                "is_active": True,
                "created": "2022-11-01T22:05:47.082806Z"
            },
            None,
        )
        self.course_overview_mock.objects.get.return_value.effort = 10
        course_id = "course-v1:test+Cx1985+2022_T4"
        expected_data = {
            "courseId": course_id,
            "userId": self.saml_social_user.extra_data["uid"],
            "approxTotalCourseHrs": 10,
            "overallProgress": 15 / 80,
            "membershipState": True,
            "enrolledAt": "2022-11-01T22:05:47.082806Z",
            "isCompleted": False,
        }
        log_error = f"send_futurex_progress --- Successful extraction of progress_enrollment_data: {expected_data}"

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            progress_data = _generate_progress_enrollment_data(self.saml_user, course_id, False)

        self.completion_summary_mock.assert_called_with(self.saml_user, course_id)
        self.enrollment_mock.assert_called_with(username=self.saml_user.username, course_id=course_id)
        self.assertEqual(logs.output, [
            f"INFO:{tasks.__name__}:{log_error}"
        ])
        self.assertDictEqual(expected_data, progress_data)

    def test_social_user_not_found(self):
        """Test when the user has no a related social user record.

        Expected behavior:
            - completion_summary is called with the right values.
            - get_enrollment is called with the right values.
            - Log error message.
            - Returned data is as expected.
        """
        self.completion_summary_mock.return_value = []
        self.enrollment_mock.return_value = (
            {
                "is_active": True,
                "created": "2022-11-01T22:05:47.082806Z"
            },
            None,
        )
        self.course_overview_mock.objects.get.return_value.effort = 10
        course_id = "course-v1:test+Cx185+2022_T4"
        expected_data = {
            "courseId": course_id,
            "userId": 16734,
            "approxTotalCourseHrs": 10,
            "overallProgress": None,
            "membershipState": True,
            "enrolledAt": "2022-11-01T22:05:47.082806Z",
            "isCompleted": False,
        }
        log_error = (
            f"User:{self.lms_user} doesn't have a social auth record, therefore is not possible to push progress."
        )

        with self.assertLogs(tasks.__name__, level="ERROR") as logs:
            progress_data = _generate_progress_enrollment_data(self.lms_user, course_id, False)

        self.completion_summary_mock.assert_called_with(self.lms_user, course_id)
        self.enrollment_mock.assert_called_with(username=self.lms_user.username, course_id=course_id)
        self.assertEqual(logs.output, [
            f"ERROR:{tasks.__name__}:{log_error}"
        ])
        self.assertDictEqual(expected_data, progress_data)


class EmitSubsectionAttemptEventTaskTestCase(unittest.TestCase):
    """Test class for emit_subsection_attempt_event_task method."""

    def setUp(self):
        """Setup common conditions for every test case"""
        self.usage_key = UsageKey.from_string(
            "block-v1:edx+CS105+2023-T3+type@problem+block@0221040b086c4618b6b2b2a554558",
        )
        self.user, _ = User.objects.get_or_create(username="Petunia")
        self.mock_components = generate_list_mock_data([
            {
                "location": "block-v1:edx+CS105+2023-T3+type@problem+block@0221040b086c4618b6b2b2a554558",
            },
            {
                "location": "block-v1:edx+CS105+2023-T3+type@problem+block@0456sdaads040b086fsdf2a554ayu",
            },
            {
                "location": "block-v1:edx+CS105+2023-T3+type@problem+block@08751040b086c4618sdfsdfsd15re8",
            },
        ])
        self.mock_unit = Mock()
        self.mock_unit.get_children.return_value = self.mock_components

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()
        SubsectionGradeFactory.reset_mock()
        get_student_module_as_dict.reset_mock()

    def mock_validations(self):
        """This method contains general mock validations for the emit_subsection_attempt_event method."""
        # 1. modulestore was called once.
        modulestore.assert_called_once()

        store = modulestore()

        # 2. get_parent_location was once with the usage key
        get_parent_location = store.get_parent_location
        get_parent_location.assert_called_once_with(self.usage_key)

        parent_location = get_parent_location()

        # 3. get_item was once with the result of get_parent_location.
        get_item = store.get_item
        get_item.assert_called_once_with(parent_location)

        # 4. get_parent was called once.
        vertical = get_item()
        vertical.get_parent.assert_called_once()

        subsection = vertical.get_parent()

        # 5. get_course was once with the course key.
        get_course = store.get_course
        get_course.assert_called_once_with(self.usage_key.course_key)

        course = get_course()

        # 6. SubsectionGradeFactory was called once with the user instance and the result of get_course method.
        SubsectionGradeFactory.assert_called_once_with(self.user, course=course)

        subsection_grade_factory = SubsectionGradeFactory()

        # 7. subsection_grade_factory create method was called once with the result of vertical.get_parent(),
        # read_only equal to True and force_calculate equal to True.
        subsection_grade_factory.create.assert_called_once_with(
            subsection=subsection,
            read_only=True,
            force_calculate=True,
        )

    @patch("eox_nelp.signals.tasks.tracker")
    def test_event_is_not_emitted(self, tracker_mock):
        """
        This tests when the subsection is not graded
        therefore the event is not emitted.

        Expected behavior:
            - tracking.emit method is not called.
            - mock validations passes.
        """
        subsection_grade = Mock(graded=False)
        SubsectionGradeFactory.return_value.create.return_value = subsection_grade

        emit_subsection_attempt_event_task(str(self.usage_key), self.user.id)

        tracker_mock.emit.assert_not_called()
        self.mock_validations()

    @patch("eox_nelp.signals.tasks.tracker")
    def test_event_is_emitted(self, tracker_mock):
        """
        This tests when the subsection is gradable and the event is emitted

        Expected behavior:
            - tracking.emit method is called with the right values.
            - mock validations passes.
        """
        modulestore.return_value.get_item.return_value.get_parent.return_value.get_children.return_value = [
            self.mock_unit,
        ]
        get_student_module_as_dict.return_value = {"attempts": 1}
        graded_total = Mock(earned=15, possible=30)
        subsection_grade = Mock(
            graded=True,
            percent_graded=50,
            graded_total=graded_total,
            location="block-v1:test+CS501+2022_T4+type@sequential+block@a54730a9b89f420a8d0343dd581b447a",
        )
        SubsectionGradeFactory.return_value.create.return_value = subsection_grade

        emit_subsection_attempt_event_task(str(self.usage_key), self.user.id)

        tracker_mock.emit.assert_called_once_with(
            "nelc.eox_nelp.grades.subsection.submitted",
            {
                "user_id": self.user.id,
                "course_id": str(self.usage_key.context_key),
                "block_id": str(subsection_grade.location),
                "submitted_at": timezone.now().strftime("%Y-%m-%d, %H:%M:%S"),
                "earned": graded_total.earned,
                "possible": graded_total.possible,
                "percent": subsection_grade.percent_graded,
                "attempts": len(self.mock_components)
            }
        )
        self.mock_validations()


@ddt
class UpdateMtTrainingStageTestCase(unittest.TestCase):
    """Test class for update_mt_training_stage function"""

    def setUp(self):
        """Set common conditions for test cases."""
        self.course_id = "course-v1:test+Cx105+2022_T4"
        self.national_id = "1245789652"
        self.stage_result = 1

    def tearDown(self):
        """Drop the delivery records after every test to keep standard conditions"""
        MTTrainingStageDelivery.objects.all().delete()  # pylint: disable=no-member

    @staticmethod
    def build_response(response_code):
        """Build an API response with the given response code."""
        return {
            "correlationID": "abc-123",
            "responseCode": response_code,
            "responseMessage": "Success" if response_code == 100 else "Registration not found",
            "data": {"result": "true" if response_code == 100 else "false"},
        }

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_update_training_stage_call(self, api_mock):
        """Test when the feature flag has been set and the API call has been executed.

        Expected behavior:
            - MinisterOfTourismApiClient mock has been called once.
            - update_training_stage was called with the right parameters.
            - logger.info outputs the expected log message.
        """
        response_mock = self.build_response(100)
        api_mock.return_value.update_training_stage.return_value = response_mock
        log_msg = (
            f"Called update_training_stage with course_id={self.course_id}, "
            f"national_id={self.national_id}, stage_result={self.stage_result}. "
            f"Response: {response_mock}"
        )

        with self.assertLogs("eox_nelp.signals.tasks", level="INFO") as logs:
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=self.national_id,
                stage_result=self.stage_result,
            )

        api_mock.assert_called_once()
        api_mock.return_value.update_training_stage.assert_called_once_with(
            course_id=self.course_id,
            national_id=self.national_id,
            stage_result=self.stage_result,
        )
        self.assertEqual(logs.output, [f"INFO:eox_nelp.signals.tasks:{log_msg}"])

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_acknowledged_result_is_not_sent_again(self, api_mock):
        """Test that a result already acknowledged by the API is not sent a second time.

        Expected behavior:
            - update_training_stage was called only once for the two executions.
        """
        api_mock.return_value.update_training_stage.return_value = self.build_response(100)

        for _ in range(2):
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=self.national_id,
                stage_result=self.stage_result,
            )

        api_mock.return_value.update_training_stage.assert_called_once()

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_unacknowledged_result_raises(self, api_mock):
        """Test when the API answers with a response code which is not the success one.

        Expected behavior:
            - MTTrainingStageError is raised.
            - logger.error outputs the expected log message.
        """
        response_mock = self.build_response(110)
        api_mock.return_value.update_training_stage.return_value = response_mock
        log_msg = (
            f"Failed update_training_stage with course_id={self.course_id}, "
            f"national_id={self.national_id}, stage_result={self.stage_result}. "
            f"Response: {response_mock}"
        )

        with self.assertLogs("eox_nelp.signals.tasks", level="ERROR") as logs:
            with self.assertRaises(MTTrainingStageError):
                update_mt_training_stage(
                    course_id=self.course_id,
                    national_id=self.national_id,
                    stage_result=self.stage_result,
                )

        self.assertEqual(logs.output, [f"ERROR:eox_nelp.signals.tasks:{log_msg}"])

    @patch("eox_nelp.signals.tasks.current_task")
    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_retry_is_not_skipped_by_the_delivery_record(self, api_mock, current_task_mock):
        """Test that a retry of an unacknowledged result is sent even inside the retry window.

        Expected behavior:
            - update_training_stage was called, so the retries are not turned into no-ops.
        """
        current_task_mock.request.retries = 1
        api_mock.return_value.update_training_stage.return_value = self.build_response(110)
        MTTrainingStageDelivery.objects.create(  # pylint: disable=no-member
            national_id=self.national_id,
            course_id=self.course_id,
            stage_result=self.stage_result,
            attempts=1,
        )

        with self.assertRaises(MTTrainingStageError):
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=self.national_id,
                stage_result=self.stage_result,
            )

        api_mock.return_value.update_training_stage.assert_called_once()

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_acknowledged_result_is_never_sent_again(self, api_mock):
        """Test that a result the partner already accepted is not delivered a second time.

        Expected behavior:
            - update_training_stage was not called.
        """
        MTTrainingStageDelivery.objects.create(  # pylint: disable=no-member
            national_id=self.national_id,
            course_id=self.course_id,
            stage_result=self.stage_result,
            attempts=1,
            acknowledged=True,
        )

        update_mt_training_stage(
            course_id=self.course_id,
            national_id=self.national_id,
            stage_result=self.stage_result,
        )

        api_mock.return_value.update_training_stage.assert_not_called()

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_acknowledgement_is_recorded(self, api_mock):
        """Test that an accepted result is marked acknowledged on its delivery record.

        Expected behavior:
            - The record is acknowledged, carries the response code and counts the attempt.
        """
        api_mock.return_value.update_training_stage.return_value = self.build_response(100)

        update_mt_training_stage(
            course_id=self.course_id,
            national_id=self.national_id,
            stage_result=self.stage_result,
        )

        delivery = MTTrainingStageDelivery.objects.get(  # pylint: disable=no-member
            national_id=self.national_id,
            course_id=self.course_id,
            stage_result=self.stage_result,
        )
        self.assertTrue(delivery.acknowledged)
        self.assertIsNotNone(delivery.acknowledged_at)
        self.assertEqual(delivery.last_response_code, "100")
        self.assertEqual(delivery.attempts, 1)

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_rejection_is_recorded_and_left_unacknowledged(self, api_mock):
        """Test that a rejected result stays unacknowledged so it can be reconciled.

        Expected behavior:
            - The record is not acknowledged and carries the rejection code.
        """
        api_mock.return_value.update_training_stage.return_value = self.build_response(110)

        with self.assertRaises(MTTrainingStageError):
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=self.national_id,
                stage_result=self.stage_result,
            )

        delivery = MTTrainingStageDelivery.objects.get(  # pylint: disable=no-member
            national_id=self.national_id,
            course_id=self.course_id,
            stage_result=self.stage_result,
        )
        self.assertFalse(delivery.acknowledged)
        self.assertEqual(delivery.last_response_code, "110")

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_a_missing_response_code_is_stored_as_null(self, api_mock):
        """Test that a response carrying no code leaves last_response_code empty.

        Storing `str(None)` would write the four-character string "None", which reads
        like a real code and is missed by an isnull lookup.

        Expected behavior:
            - last_response_code is None, not the string "None".
        """
        api_mock.return_value.update_training_stage.return_value = {"responseMessage": "gateway timeout"}

        with self.assertRaises(MTTrainingStageError):
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=self.national_id,
                stage_result=self.stage_result,
            )

        delivery = MTTrainingStageDelivery.objects.get(  # pylint: disable=no-member
            national_id=self.national_id,
            course_id=self.course_id,
            stage_result=self.stage_result,
        )
        self.assertIsNone(delivery.last_response_code)

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_a_corrected_national_id_is_delivered_again(self, api_mock):
        """Test that correcting a learner's national ID produces a new delivery.

        The partner identifies a learner by the value we send, so an acknowledgement
        of the old value must not suppress the corrected one.

        Expected behavior:
            - update_training_stage was called for the corrected id.
        """
        MTTrainingStageDelivery.objects.create(  # pylint: disable=no-member
            national_id="1245789652",
            course_id=self.course_id,
            stage_result=self.stage_result,
            attempts=1,
            acknowledged=True,
        )
        api_mock.return_value.update_training_stage.return_value = self.build_response(100)

        update_mt_training_stage(
            course_id=self.course_id,
            national_id="1245789653",
            stage_result=self.stage_result,
        )

        api_mock.return_value.update_training_stage.assert_called_once()

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_national_id_is_normalized(self, api_mock):
        """Test that an Arabic-Indic national_id is translated before it is sent.

        Expected behavior:
            - update_training_stage was called with the ASCII representation.
        """
        api_mock.return_value.update_training_stage.return_value = self.build_response(100)

        update_mt_training_stage(
            course_id=self.course_id,
            national_id="١٠٠٥٢٧٦٩٧٥",
            stage_result=self.stage_result,
        )

        api_mock.return_value.update_training_stage.assert_called_once_with(
            course_id=self.course_id,
            national_id="1005276975",
            stage_result=self.stage_result,
        )

    @data("000000", "0000000000", "3005276975", "not-a-national-id", "")
    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_invalid_national_id_is_not_sent(self, national_id, api_mock):
        """Test that a national_id which does not match the national ID shape is not sent.

        Expected behavior:
            - MinisterOfTourismApiClient mock has not been called.
            - logger.error outputs the expected log message.
        """
        log_msg = (
            f"Skipped update_training_stage with course_id={self.course_id}, "
            f"stage_result={self.stage_result}. Invalid national_id: {national_id}"
        )

        with self.assertLogs("eox_nelp.signals.tasks", level="ERROR") as logs:
            update_mt_training_stage(
                course_id=self.course_id,
                national_id=national_id,
                stage_result=self.stage_result,
            )

        api_mock.assert_not_called()
        self.assertEqual(logs.output, [f"ERROR:eox_nelp.signals.tasks:{log_msg}"])


@ddt
class CourseCompletionMtUpdaterTestCase(TestCase):
    """Test class for course_completion_mt_updater function."""

    def setUp(self):
        """ Set common conditions for test cases."""
        self.descriptor = Mock()
        self.course_id = "course-v1:test+Cx105+2022_T4"
        modulestore.return_value.get_course.return_value = self.descriptor

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()

    def mock_validations(self):
        """This method contains general mock validations for the course_completion_mt_updater function."""
        # 1. modulestore was called once.
        modulestore.assert_called_once()

        store = modulestore()

        # 2. get_course was called once with the usage key
        course_key = CourseKey.from_string(self.course_id)
        store.get_course.assert_called_once_with(course_key)

    @data(([], True), ([1, 2, 3], False))
    @patch("eox_nelp.signals.utils.get_completion_summary")
    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_invalid_grading_conditions(self, test_data, updater_mock, completion_summary_mock):
        """Test when following conditions are not met:
            1. Course is graded and the force_graded parameter is False.
            2. Course is not graded and the force_graded parameter is True.

        Expected behavior:
            - update_mt_training_stage mock has not been called.
            - mock validators pass
        """
        user_instance, _ = User.objects.get_or_create(username="1245789652")
        completion_summary_mock.return_value = {"incomplete_count": 0}
        self.descriptor.grading_policy = {"GRADER": test_data[0]}

        course_completion_mt_updater(
            user_id=user_instance.id,
            course_id=self.course_id,
            stage_result=1,
            force_graded=test_data[1],
        )

        updater_mock.assert_not_called()

    @patch("eox_nelp.signals.utils.get_completion_summary")
    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_invalid_completion_summary(self, updater_mock, completion_summary_mock):
        """Test when completion summary incomplete count is different from 0.

        Expected behavior:
            - update_mt_training_stage mock has not been called.
            - mock validations pass
        """
        user_instance, _ = User.objects.get_or_create(username="1245789652")
        completion_summary_mock.return_value = {"incomplete_count": 15}
        self.descriptor.grading_policy = {"GRADER": []}

        course_completion_mt_updater(
            user_id=user_instance.id,
            course_id=self.course_id,
            stage_result=1,
        )

        updater_mock.assert_not_called()
        self.mock_validations()

    @data(([1, 2, 3], True), ([], False))
    @patch("eox_nelp.signals.utils.get_completion_summary")
    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_update_mt_training_stage_call(self, test_data, updater_mock, completion_summary_mock):
        """Test when following conditions are met and the update_mt_training_stage is called.
            1. The course has been completed, is graded and the parameter force_graded is True.
            2. The course has been completed, is not graded and the parameter force_graded is False.

        Expected behavior:
            - update_mt_training_stage was called with the right parameters.
            - mock validations pass
        """
        user_instance, _ = User.objects.get_or_create(username="Minerva")
        ExtraInfo.objects.get_or_create(  # pylint: disable=no-member
            user=user_instance,
            arabic_name="مسؤل",
            national_id="12345445522",
        )
        completion_summary_mock.return_value = {"incomplete_count": 0}
        self.descriptor.grading_policy = {"GRADER": test_data[0]}

        course_completion_mt_updater(
            user_id=user_instance.id,
            course_id=self.course_id,
            stage_result=2,
            force_graded=test_data[1],
        )

        updater_mock.assert_called_once_with(
            course_id=self.course_id,
            national_id=user_instance.extrainfo.national_id,
            stage_result=2,
        )
        self.mock_validations()


class SetDefaultAdvancedModulesTestCase(TestCase):
    """Test class for set_default_advanced_modules function."""

    def setUp(self):
        """ Set common conditions for test cases."""
        self.user, _ = User.objects.get_or_create(username="1245789652")
        self.course_id = "course-v1:test+Cx105+2022_T4"

    def tearDown(self):
        """Restore mocks' state"""
        modulestore.reset_mock()

    @patch("eox_nelp.signals.tasks.configuration_helpers")
    def test_successful_updating(self, configuration_helpers_mock):
        """
        Test that the course's advanced modules has been updated successfully

        Expected behavior:
            - modulestore's get_course method has been called once with a CourseLocator.
            - configuration_helpers' get_value_for_org method has been called with the right data.
            - the advanced_modules contains the expect elements.
            - modulestore's update_item method has been called once with the right data.
        """
        store = modulestore()
        course = Mock()
        course.advanced_modules = ["sga", "ora", "gradebook"]
        store.get_course.return_value = course
        course_key = CourseKey.from_string(self.course_id)
        configuration_helpers_mock.get_value_for_org.return_value = [
            "completion",
            "checkboxes",
            "html",
            "gradebook",
        ]

        set_default_advanced_modules(user_id=self.user.id, course_id=self.course_id)

        store.get_course.assert_called_once_with(course_key)
        configuration_helpers_mock.get_value_for_org.assert_called_once_with(
            course_key.org,
            "DEFAULT_ADVANCED_MODULES",
            [],
        )
        self.assertCountEqual(
            course.advanced_modules,
            ["sga", "ora", "gradebook", "completion", "checkboxes", "html"],
        )
        store.update_item.assert_called_once_with(course, self.user.id)


class CreateCourseModeTaskTestCase(unittest.TestCase):
    """Test class for create_course_mode Celery task."""

    def setUp(self):
        """Setup common conditions for every test case."""
        self.course_key_str = "course-v1:test+Cx105+2022_T4"
        self.course_key = CourseKey.from_string(self.course_key_str)
        self.mode_slug = "honor"

        # Create the CourseOverview in the test database
        self.course_overview = CourseOverview.objects.create(
            id=self.course_key,
            org="test"
        )

    def tearDown(self):
        """Clean up the test database after each test."""
        CourseMode.objects.all().delete()
        CourseOverview.objects.all().delete()

    def test_invalid_course_key(self):
        """Test that the task handles an invalid course key string.

        Expected behavior:
            - expected logs of InvalidKeyError
            - CourseMode count remains 0
        """
        invalid_key_str = "invalid-key-string"
        expected_log = [
            f"ERROR:{tasks.__name__}:"
            f"Cannot create course mode. Invalid course key string provided: {invalid_key_str}"
        ]

        with self.assertLogs(tasks.__name__, level="ERROR") as logs:
            create_course_mode(invalid_key_str, self.mode_slug)

        self.assertListEqual(logs.output, expected_log)
        self.assertEqual(CourseMode.objects.count(), 0)

    def test_course_overview_does_not_exist(self):
        """Test that the task handles a missing CourseOverview.

        Expected behavior:
            - expected logs of CourseOverview.DoesNotExist
            - CourseMode count remains 0
        """
        missing_key_str = "course-v1:test+MISSING+2022_T4"
        expected_log = [
            f"ERROR:{tasks.__name__}:"
            f"Cannot create course mode. CourseOverview for key {missing_key_str} does not exist."
        ]

        with self.assertLogs(tasks.__name__, level="ERROR") as logs:
            create_course_mode(missing_key_str, self.mode_slug)

        self.assertListEqual(logs.output, expected_log)
        self.assertEqual(CourseMode.objects.count(), 0)

    def test_course_mode_created_successfully(self):
        """Test that the CourseMode is successfully created.

        Expected behavior:
            - expected logs of successful creation
            - the desired CourseMode object exists in the database
        """
        expected_log = [
            f"INFO:{tasks.__name__}:"
            f"Successfully created '{self.mode_slug}' course mode for course {self.course_key_str}"
        ]

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            create_course_mode(self.course_key_str, self.mode_slug)

        self.assertListEqual(logs.output, expected_log)
        self.assertTrue(
            CourseMode.objects.filter(
                course=self.course_overview,
                mode_slug=self.mode_slug
            ).exists()
        )

    def test_course_mode_already_exists(self):
        """Test that the task handles an already existing CourseMode.

        Expected behavior:
            - expected logs of already existing CourseMode
            - CourseMode count remains 1
        """
        # Create the course mode before running the task
        CourseMode.objects.create(
            course=self.course_overview,
            mode_slug=self.mode_slug,
            mode_display_name=self.mode_slug.capitalize(),
        )
        expected_log = [
            f"INFO:{tasks.__name__}:"
            f"Course mode '{self.mode_slug}' already exists for course {self.course_key_str}"
        ]

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            create_course_mode(self.course_key_str, self.mode_slug)

        self.assertListEqual(logs.output, expected_log)
        self.assertEqual(CourseMode.objects.count(), 1)


class ReconcileMtTrainingStagesTestCase(TestCase):
    """Test class for the reconcile_mt_training_stages task."""

    def setUp(self):
        """Set common conditions for test cases."""
        self.course_id = "course-v1:test+Cx105+2022_T4"
        self.national_id = "1245789652"

    def tearDown(self):
        """Drop the delivery records after every test to keep standard conditions"""
        MTTrainingStageDelivery.objects.all().delete()  # pylint: disable=no-member

    def build_delivery(self, national_id, attempts, acknowledged=False, hours_ago=12):
        """Create a delivery record whose updated_at is far enough in the past to be due."""
        delivery = MTTrainingStageDelivery.objects.create(  # pylint: disable=no-member
            national_id=national_id,
            course_id=self.course_id,
            stage_result=1,
            attempts=attempts,
            acknowledged=acknowledged,
        )
        # updated_at is auto_now, so it has to be rewritten to age the row.
        MTTrainingStageDelivery.objects.filter(pk=delivery.pk).update(  # pylint: disable=no-member
            updated_at=timezone.now() - timedelta(hours=hours_ago),
        )

        return delivery

    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_nothing_outstanding_is_logged_at_info(self, task_mock):
        """Test that a run with nothing owed does not log at ERROR.

        A healthy run must not raise an alert, otherwise the level stops meaning
        anything and the alert becomes noise.

        Expected behavior:
            - The single log record is INFO.
            - Nothing was re-sent.
        """
        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            result = reconcile_mt_training_stages()

        self.assertEqual([r.split(":")[0] for r in logs.output], ["INFO"])
        self.assertEqual(result["resent"], 0)
        self.assertEqual(result["actionable"], 0)
        task_mock.delay.assert_not_called()

    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_outstanding_results_are_logged_at_error(self, task_mock):
        """Test that a result still owed raises the log level to ERROR.

        Expected behavior:
            - The log record is ERROR.
            - The result was re-sent and counted as actionable.
        """
        self.build_delivery(self.national_id, attempts=2)

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            result = reconcile_mt_training_stages()

        self.assertEqual([r.split(":")[0] for r in logs.output], ["ERROR"])
        self.assertEqual(result["resent"], 1)
        self.assertEqual(result["actionable"], 1)
        self.assertEqual(result["abandoned"], 0)
        task_mock.delay.assert_called_once()

    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_exhausted_results_are_abandoned_not_actionable(self, task_mock):
        """Test that a result which ran out of attempts stops counting as outstanding.

        Nothing will be done about it again, so counting it alongside the retryable
        ones produces a backlog that can only rise.

        Expected behavior:
            - It is reported as abandoned, not actionable.
            - The run logs at INFO, since nothing is still owed.
            - It is not re-sent.
        """
        self.build_delivery(self.national_id, attempts=tasks.MT_RECONCILE_MAX_ATTEMPTS)

        with self.assertLogs(tasks.__name__, level="INFO") as logs:
            result = reconcile_mt_training_stages()

        self.assertEqual([r.split(":")[0] for r in logs.output], ["INFO"])
        self.assertEqual(result["actionable"], 0)
        self.assertEqual(result["abandoned"], 1)
        task_mock.delay.assert_not_called()

    @patch("eox_nelp.signals.tasks.update_mt_training_stage")
    def test_acknowledged_results_are_never_resent(self, task_mock):
        """Test that an accepted result is left alone.

        Expected behavior:
            - Nothing is re-sent and nothing is outstanding.
        """
        self.build_delivery(self.national_id, attempts=1, acknowledged=True)

        result = reconcile_mt_training_stages()

        self.assertEqual(result["resent"], 0)
        self.assertEqual(result["actionable"], 0)
        self.assertEqual(result["abandoned"], 0)
        task_mock.delay.assert_not_called()
