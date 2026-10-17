"""Tests for binding a worker to the tenant of an org."""
from django.test import TestCase, override_settings
from mock import patch

from eox_nelp.learner_emails.tenant import TenantNotResolvedError, bind_tenant_for_org

MODULE = "eox_nelp.learner_emails.tenant"


class BindTenantTestCase(TestCase):
    """Binding must succeed only when eox-tenant really bound the domain."""

    @patch(f"{MODULE}.configuration_helpers")
    @patch(f"{MODULE}._update_settings")
    @patch(f"{MODULE}.can_keep_settings", return_value=False)
    @override_settings(EDNX_TENANT_DOMAIN="ksu.example.com")
    def test_binds_the_domain_of_the_org(self, _keep, update_mock, helpers_mock):
        """The domain is the host of the org's LMS_ROOT_URL and settings are updated for it."""
        helpers_mock.get_value_for_org.return_value = "https://ksu.example.com"

        self.assertEqual(bind_tenant_for_org("KSU"), "ksu.example.com")
        update_mock.assert_called_once_with("ksu.example.com", "lms_configs")

    @patch(f"{MODULE}.configuration_helpers")
    @patch(f"{MODULE}._update_settings")
    @patch(f"{MODULE}.can_keep_settings", return_value=True)
    @override_settings(EDNX_TENANT_DOMAIN="ksu.example.com")
    def test_keeps_settings_already_bound(self, _keep, update_mock, helpers_mock):
        """A worker already bound to the tenant is not rebound."""
        helpers_mock.get_value_for_org.return_value = "https://ksu.example.com"

        bind_tenant_for_org("KSU")

        update_mock.assert_not_called()

    @patch(f"{MODULE}.configuration_helpers")
    @patch(f"{MODULE}._update_settings")
    @patch(f"{MODULE}.can_keep_settings", return_value=False)
    @override_settings(EDNX_TENANT_DOMAIN="other.example.com")
    def test_fails_when_eox_tenant_did_not_bind(self, _keep, _update, helpers_mock):
        """If the settings do not end up on the tenant the mail must not be sent unbranded."""
        helpers_mock.get_value_for_org.return_value = "https://ksu.example.com"

        with self.assertRaises(TenantNotResolvedError):
            bind_tenant_for_org("KSU")

    @patch(f"{MODULE}.configuration_helpers")
    def test_fails_without_a_domain(self, helpers_mock):
        """An org whose root URL has no host cannot be resolved."""
        helpers_mock.get_value_for_org.return_value = ""

        with self.assertRaises(TenantNotResolvedError):
            bind_tenant_for_org("KSU")
