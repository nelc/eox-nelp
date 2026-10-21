"""
Test the tenant access rules.
"""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import TestCase
from edx_toggles.toggles.testutils import override_waffle_switch
from rest_framework.exceptions import NotFound

from eox_nelp.access import (
    ENFORCE_STATS_STAFF_ONLY,
    GLOBAL_LOOKUP_GROUP,
    TENANT_STAFF_ROLES,
    TenantStaffOrLogOnly,
    evaluate_rule,
    has_global_lookup,
    is_tenant_member,
    is_tenant_staff,
)

User = get_user_model()


class GlobalLookupTestCase(TestCase):
    """Test case for has_global_lookup."""

    def setUp(self):
        """Setup common conditions for every test case."""
        self.user = User.objects.create_user(username="caller", email="caller@example.com")

    def test_anonymous_user(self):
        """An anonymous user never has global lookup."""
        self.assertFalse(has_global_lookup(AnonymousUser()))

    def test_staff_user_is_not_enough(self):
        """A platform staff user without the group has no global lookup."""
        self.user.is_staff = True

        self.assertFalse(has_global_lookup(self.user))

    def test_superuser(self):
        """A superuser has global lookup."""
        self.user.is_superuser = True

        self.assertTrue(has_global_lookup(self.user))

    def test_group_member(self):
        """A member of the allow-list group has global lookup."""
        self.user.groups.add(Group.objects.create(name=GLOBAL_LOOKUP_GROUP))

        self.assertTrue(has_global_lookup(self.user))


class TenantMemberTestCase(TestCase):
    """Test case for is_tenant_member."""

    @patch("eox_nelp.access.get_edxapp_user")
    def test_member(self, get_edxapp_user_mock):
        """
        A user that eox-core finds on the site is a member.

        Expected behavior:
            - eox-core is asked with the username and the site.
        """
        site = Mock()
        user = Mock(username="learner")

        self.assertTrue(is_tenant_member(user, site))
        get_edxapp_user_mock.assert_called_once_with(username="learner", site=site)

    @patch("eox_nelp.access.get_edxapp_user", side_effect=NotFound)
    def test_not_member(self, _get_edxapp_user_mock):
        """A user that eox-core does not find on the site is not a member."""
        self.assertFalse(is_tenant_member(Mock(username="learner"), Mock()))


@patch("eox_nelp.access.CourseAccessRole")
@patch("eox_nelp.access.configuration_helpers")
class TenantStaffTestCase(TestCase):
    """Test case for is_tenant_staff."""

    def setUp(self):
        """Setup common conditions for every test case."""
        self.user = User.objects.create_user(username="author", email="author@example.com")

    def test_anonymous_user(self, _helpers_mock, _role_mock):
        """An anonymous user is not tenant staff."""
        self.assertFalse(is_tenant_staff(AnonymousUser()))

    def test_platform_staff(self, _helpers_mock, role_mock):
        """
        Platform staff is tenant staff without a role lookup.

        Expected behavior:
            - True.
            - No course access role query.
        """
        self.user.is_staff = True

        self.assertTrue(is_tenant_staff(self.user))
        role_mock.objects.filter.assert_not_called()

    def test_role_in_tenant_org(self, helpers_mock, role_mock):
        """
        A staff role in an org of the tenant makes the user tenant staff.

        Expected behavior:
            - True.
            - The roles are filtered by user and by the staff role set.
        """
        helpers_mock.get_current_site_orgs.return_value = ["OrgA"]
        role_mock.objects.filter.return_value.exists.return_value = True

        self.assertTrue(is_tenant_staff(self.user))
        _, kwargs = role_mock.objects.filter.call_args
        self.assertEqual(kwargs, {"user": self.user, "role__in": TENANT_STAFF_ROLES})

    def test_no_role_in_tenant_org(self, helpers_mock, role_mock):
        """A user without a staff role in the tenant orgs is not tenant staff."""
        helpers_mock.get_current_site_orgs.return_value = ["OrgA"]
        role_mock.objects.filter.return_value.exists.return_value = False

        self.assertFalse(is_tenant_staff(self.user))

    def test_tenant_without_orgs(self, helpers_mock, role_mock):
        """
        On a site with no orgs nobody but platform staff is tenant staff.

        Expected behavior:
            - False.
            - No course access role query (an empty org filter would match every org).
        """
        helpers_mock.get_current_site_orgs.return_value = []

        self.assertFalse(is_tenant_staff(self.user))
        role_mock.objects.filter.assert_not_called()


class EvaluateRuleTestCase(TestCase):
    """Test case for evaluate_rule."""

    def test_allowed(self):
        """An allowed request is never refused, whatever the switch."""
        audit_extra = {}

        with override_waffle_switch(ENFORCE_STATS_STAFF_ONLY, True):
            refused = evaluate_rule(ENFORCE_STATS_STAFF_ONLY, "rule", True, audit_extra)

        self.assertFalse(refused)
        self.assertEqual(audit_extra, {"rule": "allow"})

    def test_denied_log_only(self):
        """A failing rule is only logged while its switch is off."""
        audit_extra = {}

        with override_waffle_switch(ENFORCE_STATS_STAFF_ONLY, False):
            refused = evaluate_rule(ENFORCE_STATS_STAFF_ONLY, "rule", False, audit_extra)

        self.assertFalse(refused)
        self.assertEqual(audit_extra, {"rule": "would_deny"})

    def test_denied_enforced(self):
        """A failing rule refuses the request once its switch is on."""
        audit_extra = {}

        with override_waffle_switch(ENFORCE_STATS_STAFF_ONLY, True):
            refused = evaluate_rule(ENFORCE_STATS_STAFF_ONLY, "rule", False, audit_extra)

        self.assertTrue(refused)
        self.assertEqual(audit_extra, {"rule": "deny"})


@patch("eox_nelp.access.is_tenant_staff", return_value=False)
class TenantStaffOrLogOnlyTestCase(TestCase):
    """Test case for the TenantStaffOrLogOnly permission."""

    def test_log_only(self, _staff_mock):
        """
        A non-staff caller passes while the switch is off.

        Expected behavior:
            - Permission granted.
            - The verdict is recorded on the view.
        """
        view = Mock(audit_extra={})

        granted = TenantStaffOrLogOnly().has_permission(Mock(), view)

        self.assertTrue(granted)
        self.assertEqual(view.audit_extra, {"stats_staff_only": "would_deny"})

    def test_enforced(self, _staff_mock):
        """A non-staff caller is refused once the switch is on."""
        view = Mock(audit_extra={})

        with override_waffle_switch(ENFORCE_STATS_STAFF_ONLY, True):
            granted = TenantStaffOrLogOnly().has_permission(Mock(), view)

        self.assertFalse(granted)
        self.assertEqual(view.audit_extra, {"stats_staff_only": "deny"})
