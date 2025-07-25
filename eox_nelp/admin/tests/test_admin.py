"""
Unit tests for the student admin module.

Classes:
    TestPearsonAction: Tests for pearson_action admin actions.
    TestNelpCourseEnrollmentAdmin: Tests for the NelpCourseEnrollmentAdmin admin class.
"""
from unittest.mock import MagicMock, patch

from ddt import data, ddt, unpack
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from eox_nelp.admin import (
    NelpCourseEnrollmentAdmin,
    pearson_add_ead_action,
    pearson_cdd_action,
    pearson_delete_ead_action,
    pearson_real_time_action,
    pearson_update_ead_action,
)

User = get_user_model()


@ddt
class TestPearsonAction(TestCase):
    """
    Unit tests for the pearson actions functions.
    """

    def setUp(self):
        """Setup common conditions for every test case"""
        self.request = RequestFactory().get("/admin")

    def _create_mock_enrollment(self, course_id):
        """Create a mock course enrollment."""
        user = MagicMock()
        user.id = 1
        enrollment = MagicMock()
        enrollment.course_id = course_id
        enrollment.user = user

        return enrollment

    def _prepare_call_kwargs(self, enrollments, call_args, extra_call_kwargs):
        """Prepare the call arguments for the mocked task."""
        mocks_call_kwargs = []
        for enrollment in enrollments:
            call_kwargs = {
                "user_id": enrollment.user.id,
                "course_id": enrollment.course_id,
                "exam_id": enrollment.course_id,
            }
            # Retain only required arguments and update with extra kwargs
            call_kwargs = {key: call_kwargs[key] for key in call_args if key in call_kwargs}
            call_kwargs.update(extra_call_kwargs)
            mocks_call_kwargs.append(call_kwargs)

        return mocks_call_kwargs

    def _assert_mocked_task_calls(self, mocked_task, mocks_call_kwargs):
        """Assert that the mocked task was called with the correct parameters."""
        for mock_call_kwargs in mocks_call_kwargs:
            mocked_task.assert_any_call(**mock_call_kwargs)
        self.assertEqual(mocked_task.call_count, len(mocks_call_kwargs))

    @data(
        {
            "admin_action": pearson_real_time_action,
            "call_args": ["user_id", "exam_id"],
            "extra_call_kwargs": {
                "action_name": "rti",
            },
        },
        {
            "admin_action": pearson_add_ead_action,
            "call_args": ["user_id", "exam_id"],
            "extra_call_kwargs": {
                "transaction_type": "Add",
                "action_name": "ead",
            },

        },
        {
            "admin_action": pearson_update_ead_action,
            "call_args": ["user_id", "exam_id"],
            "extra_call_kwargs": {
                "transaction_type": "Update",
                "action_name": "ead",
            },
        },
        {
            "admin_action": pearson_delete_ead_action,
            "call_args": ["user_id", "exam_id"],
            "extra_call_kwargs": {
                "transaction_type": "Delete",
                "action_name": "ead",
            },
        },
        {
            "admin_action": pearson_cdd_action,
            "call_args": ["user_id"],
            "extra_call_kwargs": {
                "action_name": "cdd",
            },
        },
    )
    @unpack
    @override_settings(USE_PEARSON_ENGINE_SERVICE=True)
    def test_pearson_course_enrollment_action_v2(self, admin_action, call_args, extra_call_kwargs):
        """
        Test that a pearson_action function calls a task delay with correct parameters.
        """
        queryset = [
            self._create_mock_enrollment("course-v1:TestX+T101+2024_T1"),
            self._create_mock_enrollment("course-v1:FutureX+T102+2025_T1"),
        ]
        mocks_call_kwargs = self._prepare_call_kwargs(queryset, call_args, extra_call_kwargs)

        # Call the admin action
        with patch("eox_nelp.pearson_vue_engine.tasks.real_time_import_task_v2.delay") as mocked_task:
            admin_action(MagicMock(), self.request, queryset)
            self._assert_mocked_task_calls(mocked_task, mocks_call_kwargs)


@ddt
class TestNelpCourseEnrollmentAdmin(TestCase):
    """
    Unit tests for the NelpCourseEnrollmentAdmin class.
    """

    def setUp(self):
        """
        Set up test environment.
        """
        self.modeladmin = NelpCourseEnrollmentAdmin()

    @data(
        pearson_add_ead_action,
        pearson_cdd_action,
        pearson_delete_ead_action,
        pearson_real_time_action,
        pearson_update_ead_action,
    )
    @override_settings(USE_PEARSON_ENGINE_SERVICE=True)
    def test_actions(self, admin_action):
        """
        Test that the actions list contains pearson_real_time_action.

        Expected behavior:
            - pearson_real_time_action method is in model actions.
        """
        self.assertIn(admin_action, self.modeladmin.actions)


class TestNelpUserAdmin(TestCase):
    """
    Unit tests for the NelpUserAdmin class.
    """

    def test_load_module(self):
        """
        Test loading module of NelpUserAdmin when eox_support condition is bypassed.

        Expected behavior:
            - Test NelpUserAdmin is loaded in the user model key of admin registry.
            - user_national_id is in list_display
            - UserExtraInfoInline in inlines
        """
        class ProtoAdminUserSupportModule:
            """Proto class to simulate module"""
            class SupportUserAdmin(admin.ModelAdmin):
                """Base User Model admin for testing purposes. With empty tuple to add the nelp values"""
                list_display = ((),)
                search_fields = ((),)
                inlines = ((),)
                readonly_fields = ((),)

        with patch.dict("sys.modules", {"eox_support.admin.user": ProtoAdminUserSupportModule}):
            from eox_nelp.admin.user import (  # pylint: disable=import-outside-toplevel
                NelpUserAdmin,
                UserExtraInfoInline,
            )

            self.assertIsInstance(admin.site._registry[User], NelpUserAdmin)  # pylint: disable=protected-access
            self.assertIn("user_national_id", NelpUserAdmin.list_display)
            self.assertIn(UserExtraInfoInline, NelpUserAdmin.inlines)
