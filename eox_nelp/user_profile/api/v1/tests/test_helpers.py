"""
This file contains the tests for the user_profile API V1 helpers.py file.

Test Cases:
    - HoldsInstitutionRoleTestCase: Tests for holds_institution_role.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from opaque_keys.edx.django.models import CourseKeyField

from eox_nelp.user_profile.api.v1.helpers import holds_institution_role

User = get_user_model()


class HoldsInstitutionRoleTestCase(TestCase):
    """Test case for holds_institution_role."""

    def setUp(self):
        """Create a user."""
        self.user = User.objects.create(username="obiwan")

    @patch("eox_nelp.user_profile.api.v1.helpers.CourseAccessRole")
    def test_org_level_role_found(self, course_access_role_mock):
        """
        Test that an org-level role of a locked kind is reported.

        Expected behavior:
            - Returns the result of the exists() query.
            - The query filters by user, by CourseKeyField.Empty (never None or __isnull, which
              CourseKeyField refuses at query time) and by the default locked roles.
        """
        course_access_role_mock.objects.filter.return_value.exists.return_value = True

        self.assertTrue(holds_institution_role(self.user))
        call = course_access_role_mock.objects.filter.call_args
        self.assertEqual(call.args, ())
        self.assertEqual(call.kwargs["user"], self.user)
        self.assertIs(call.kwargs["course_id"], CourseKeyField.Empty)
        self.assertEqual(
            sorted(call.kwargs["role__in"]),
            ["data_researcher", "instructor", "org_course_creator_group", "staff"],
        )

    @patch("eox_nelp.user_profile.api.v1.helpers.CourseAccessRole")
    def test_no_role(self, course_access_role_mock):
        """
        Test that a user without such a role is not reported.

        Expected behavior:
            - Returns False.
        """
        course_access_role_mock.objects.filter.return_value.exists.return_value = False

        self.assertFalse(holds_institution_role(self.user))

    @override_settings(EOX_NELP_NATIONAL_ID_LOCKED_ROLES=[])
    @patch("eox_nelp.user_profile.api.v1.helpers.CourseAccessRole")
    def test_empty_setting_disables_the_lock(self, course_access_role_mock):
        """
        Test that an empty EOX_NELP_NATIONAL_ID_LOCKED_ROLES turns the lock off.

        Expected behavior:
            - Returns False without querying roles.
        """
        self.assertFalse(holds_institution_role(self.user))
        course_access_role_mock.objects.filter.assert_not_called()
