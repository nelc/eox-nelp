"""This file contains all the test for tasks.py file.

Classes:
    GetCompletionSummaryTestCase: Test get_completion_summary method.
    GenerateProgressEnrollmentDataTestCase: Test _generate_progress_enrollment_data method.
    UpdateMtTrainingStageTestCase: Test update_mt_training_stage task.
    CourseCompletionMtUpdaterTestCase: Test course_completion_mt_updater task.
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
from social_django.models import UserSocialAuth

from eox_nelp.edxapp_wrapper.course_blocks import get_student_module_as_dict
from eox_nelp.edxapp_wrapper.grades import SubsectionGradeFactory
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.signals import tasks
from eox_nelp.signals.tasks import (
    _generate_progress_enrollment_data,
    _post_futurex_progress,
    course_completion_mt_updater,
    dispatch_futurex_progress,
    emit_subsection_attempt_event_task,
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


class UpdateMtTrainingStageTestCase(unittest.TestCase):
    """Test class for update_mt_training_stage function"""

    @patch("eox_nelp.signals.tasks.MinisterOfTourismApiClient")
    def test_update_training_stage_call(self, api_mock):
        """Test when the feature flag has been set and the api call has been executed.

        Expected behavior:
            - MinisterOfTourismApiClient mock has been called once.
            - update_training_stage was called with the right parameters.
        """
        course_id = "course-v1:test+Cx105+2022_T4"
        national_id = "1245789652"
        stage_result = 1

        update_mt_training_stage(
            course_id=course_id,
            national_id=national_id,
            stage_result=stage_result,
        )

        api_mock.assert_called_once()
        api_mock.return_value.update_training_stage.assert_called_once_with(
            course_id=course_id,
            national_id=national_id,
            stage_result=stage_result,
        )


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
