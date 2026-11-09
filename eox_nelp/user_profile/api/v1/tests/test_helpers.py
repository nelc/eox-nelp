"""
This file contains the tests for the user_profile API V1 helpers.py file.

Test Cases:
    - HoldsInstitutionRoleTestCase: Tests for holds_institution_role.
    - HoldsLockedSocialLinkTestCase: Tests for holds_locked_social_link.
    - CheckNationalIdLockTestCase: Tests for check_national_id_lock.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from opaque_keys.edx.django.models import CourseKeyField
from social_django.models import UserSocialAuth

from eox_nelp.edxapp_wrapper.user_api import errors
from eox_nelp.user_profile.api.v1.helpers import (
    NATIONAL_ID_SSO_LOCKED_MESSAGE,
    check_national_id_lock,
    holds_institution_role,
    holds_locked_social_link,
)

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


class HoldsLockedSocialLinkTestCase(TestCase):
    """Test case for holds_locked_social_link."""

    def setUp(self):
        """Create a user linked to the MT backend."""
        self.user = User.objects.create(username="mt_learner")
        UserSocialAuth.objects.create(user=self.user, provider="config-based-openidconnect-PKCE", uid="mt-1")

    @override_settings(EOX_NELP_NATIONAL_ID_LOCKED_SOCIAL_PROVIDERS=["config-based-openidconnect-PKCE"])
    def test_listed_provider_link_found(self):
        """
        Test that a link to a listed provider is reported.

        Expected behavior:
            - Returns True.
        """
        self.assertTrue(holds_locked_social_link(self.user))

    @override_settings(EOX_NELP_NATIONAL_ID_LOCKED_SOCIAL_PROVIDERS=["tpa-saml"])
    def test_other_provider_link_ignored(self):
        """
        Test that a link to a provider that is not listed is not reported.

        Expected behavior:
            - Returns False.
        """
        self.assertFalse(holds_locked_social_link(self.user))

    def test_default_setting_disables_the_lock(self):
        """
        Test that the lock is off unless the setting lists a provider.

        Expected behavior:
            - Returns False.
        """
        self.assertFalse(holds_locked_social_link(self.user))


@override_settings(EOX_NELP_NATIONAL_ID_LOCKED_SOCIAL_PROVIDERS=["config-based-openidconnect-PKCE"])
@patch("eox_nelp.user_profile.api.v1.helpers.holds_institution_role", return_value=False)
class CheckNationalIdLockTestCase(TestCase):
    """Test case for check_national_id_lock with a social link lock."""

    def setUp(self):
        """Create a user linked to the MT backend."""
        self.user = User.objects.create(username="mt_learner")
        UserSocialAuth.objects.create(user=self.user, provider="config-based-openidconnect-PKCE", uid="mt-1")

    def test_change_refused_for_linked_learner(self, _):
        """
        Test that an MT-linked learner cannot set or change the national_id by hand.

        Expected behavior:
            - AccountValidationError with the SSO lock message.
        """
        with self.assertRaises(errors.AccountValidationError) as context:
            check_national_id_lock(self.user, {"national_id": "1043822608"})

        self.assertIn(NATIONAL_ID_SSO_LOCKED_MESSAGE, str(context.exception))

    def test_other_fields_allowed_for_linked_learner(self, _):
        """
        Test that the lock only concerns national_id.

        Expected behavior:
            - No error is raised.
        """
        check_national_id_lock(self.user, {"arabic_first_name": "أناكين"})
