"""

This module contains unit tests for the functionality of the SAMLBulkTemplateConfiguration model.
Tests are organized by model method and ensure correct behavior across its interface for managing
SAML configurations across multiple Django sites.
"""

import json

from django.contrib.sites.models import Site
from django.test import TestCase
from mock import ANY, Mock, call, patch

from eox_nelp.edxapp_wrapper.third_party_auth import models as tpa_models
from eox_nelp.third_party_auth.models import SAMLBulkTemplateConfiguration


class TestSAMLBulkTemplateConfiguration(TestCase):
    """
    Unit tests for the SAMLBulkTemplateConfiguration model methods.
    """

    def tearDown(self):
        # Reset mocks on tpa_models so each test is isolated
        tpa_models.SAMLConfiguration.objects.reset_mock()
        tpa_models.SAMLProviderConfig.objects.reset_mock()

    def test_generate_slug_for_standard_domain(self):
        """
        Test the slug is correctly generated from a standard domain.

        Expected behavior:
            - Removes the TLD from the domain.
            - Joins the remaining parts with hyphens.
            - Appends '-lms-sso' suffix.
        """
        template = SAMLBulkTemplateConfiguration(name="Example")
        site = Site(domain="bc.futurex.sa", name="Test Site")

        result = template.generate_slug_for_site(site)

        self.assertEqual(result, "bc-futurex-lms-sso")

    def test_generate_slug_with_subdomain(self):
        """
        Test the slug is correctly generated when domain has subdomains.

        Expected behavior:
            - All parts except the TLD are joined with hyphens.
            - Appends '-lms-sso' suffix.
        """
        template = SAMLBulkTemplateConfiguration(name="Example")
        site = Site(domain="idp.bc.futurex.sa", name="Test Site")

        result = template.generate_slug_for_site(site)

        self.assertEqual(result, "idp-bc-futurex-lms-sso")

    def test_generate_slug_with_missing_tld(self):
        """
        Test the slug generation when domain has no TLD (e.g., 'localhost').

        Expected behavior:
            - Uses the domain as-is without removing any parts.
            - Appends '-lms-sso' suffix.
        """
        template = SAMLBulkTemplateConfiguration(name="Example")
        site = Site(domain="localhost", name="Local Site")

        result = template.generate_slug_for_site(site)

        self.assertEqual(result, "localhost-lms-sso")

    def test_generate_configuration_entity_id_for_site(self):
        """
        Test generation of configuration entity ID for a given site.

        Expected behavior:
            - Prepends 'https://saml.' to the full site domain.
            - Returns a full URL suitable for use as entity_id.
        """
        template = SAMLBulkTemplateConfiguration(name="Example")
        site = Site(domain="bc.futurex.sa", name="Futurex Site")

        result = template.generate_configuration_entity_id_for_site(site)

        self.assertEqual(result, "https://saml.bc.futurex.sa")

    def test_generate_organization_info_for_site_valid_json(self):
        """
        Test organization info rendering with a valid JSON template.

        Expected behavior:
            - Formats all template values by replacing '{domain}' with the site's domain.
            - Returns a stringified JSON with the domain correctly injected.
        """
        template = SAMLBulkTemplateConfiguration(
            name="Example",
            organization_info_template=(
                '{"en-US": {"url": "http://{domain}", "displayname": "Example Inc.", "name": "example"}}'
            ),
        )
        site = Site(domain="bc.futurex.sa", name="Futurex Site")
        expected = (
            '{\n'
            '  "en-US": {\n'
            '    "url": "http://bc.futurex.sa",\n'
            '    "displayname": "Example Inc.",\n'
            '    "name": "example"\n'
            '  }\n'
            '}'
        )

        result = template.generate_organization_info_for_site(site)

        self.assertEqual(result, expected)

    def test_generate_organization_info_for_site_invalid_json(self):
        """
        Test organization info rendering when the template is invalid JSON.

        Expected behavior:
            - Returns the raw template string unmodified.
        """
        template = SAMLBulkTemplateConfiguration(
            name="Invalid",
            organization_info_template='invalid-json-{domain}'
        )
        site = Site(domain="example.com", name="Example Site")

        result = template.generate_organization_info_for_site(site)

        self.assertEqual(result, 'invalid-json-{domain}')

    def test_create_or_update_saml_configuration_new_instance(self):
        """
        Test creation of a new SAMLConfiguration when none exists.

        Expected behavior:
            - Calls `update_or_create` with correct parameters.
            - Passes site, slug, and defaults with generated values.
            - Returns the created SAMLConfiguration.
        """
        mock_manager = tpa_models.SAMLConfiguration.objects.current_set.return_value
        mock_instance = Mock()
        mock_manager.update_or_create.return_value = (mock_instance, True)
        template = SAMLBulkTemplateConfiguration(
            name="Example",
            organization_info_template=json.dumps({
                "en-US": {
                    "url": "http://{domain}",
                    "displayname": "Example Inc.",
                    "name": "example"
                }
            }),
            other_config_str='{"key": "value"}',
        )
        site = Site(domain="bc.futurex.sa", name="Futurex Site")
        slug = "default"

        result = template._create_or_update_saml_configuration(site, slug)  # pylint: disable=protected-access

        self.assertEqual(result, mock_instance)
        mock_manager.update_or_create.assert_called_once_with(
            site=site,
            slug=slug,
            defaults={
                "enabled": True,
                "changed_by": None,
                "entity_id": "https://saml.bc.futurex.sa",
                "org_info_str": ANY,
                "other_config_str": '{"key": "value"}',
                "is_public": True,
            },
        )

    def test_create_or_update_saml_configuration_updates_existing(self):
        """
        Test update of an existing SAMLConfiguration instance.

        Expected behavior:
            - Returns the updated instance.
            - Calls `update_or_create` with `site`, `slug`, and updated defaults.
        """
        mock_manager = tpa_models.SAMLConfiguration.objects.current_set.return_value
        mock_instance = Mock()
        mock_manager.update_or_create.return_value = (mock_instance, False)
        template = SAMLBulkTemplateConfiguration(
            name="UpdateTest",
            organization_info_template=json.dumps({
                "en-US": {
                    "url": "http://{domain}",
                    "displayname": "Test Inc.",
                    "name": "test"
                }
            }),
            other_config_str='{"meta": "update"}',
        )
        site = Site(domain="testdomain.com", name="Test Site")
        slug = "testdomain-lms-sso"

        result = template._create_or_update_saml_configuration(site, slug)  # pylint: disable=protected-access

        self.assertEqual(result, mock_instance)
        mock_manager.update_or_create.assert_called_once()

    def test_create_or_update_provider_configuration_new_instance(self):
        """
        Test creating a new SAMLProviderConfig when none exists.

        Expected behavior:
            - Calls `update_or_create` with correct site, slug, and defaults.
            - Returns the newly created instance.
        """
        mock_manager = tpa_models.SAMLProviderConfig.objects.current_set.return_value
        mock_instance = Mock()
        mock_manager.update_or_create.return_value = (mock_instance, True)
        site = Site(domain="site.com", name="Test Site")
        slug = "site-lms-sso"
        saml_config = Mock()
        template = SAMLBulkTemplateConfiguration(
            name="Provider Template",
            icon_class="icon",
            secondary=True,
            send_welcome_email=True,
            visible=False,
            max_session_length=3600,
            sync_learner_profile_data=False,
            enable_sso_id_verification=True,
            disable_for_enterprise_sso=True,
            backend_name="custom-saml",
            entity_id="https://entity.example.com",
            metadata_source="https://metadata.example.com",
            attr_user_permanent_id="urn:uid",
            attr_full_name="urn:fullname",
            default_full_name="Default Name",
            attr_first_name="urn:fname",
            default_first_name="Default FName",
            attr_last_name="urn:lname",
            default_last_name="Default LName",
            attr_username="urn:uname",
            default_username="DefaultU",
            attr_email="urn:email",
            default_email="default@example.com",
            automatic_refresh_enabled=False,
            identity_provider_type="custom",
            country="CO",
            skip_hinted_login_dialog=False,
            skip_registration_form=False,
            skip_email_verification=False,
            send_to_registration_first=False,
            other_settings='{"extra": true}',
            archived=False,
        )

        result = template._create_or_update_provider_configuration(  # pylint: disable=protected-access
            site,
            slug,
            saml_config,
        )

        self.assertEqual(result, mock_instance)
        mock_manager.update_or_create.assert_called_once_with(
            site=site,
            archived=False,
            slug=slug,
            defaults=ANY,
        )
        # Spot check a few expected fields in defaults
        defaults = mock_manager.update_or_create.call_args.kwargs["defaults"]
        self.assertEqual(defaults["enabled"], True)
        self.assertEqual(defaults["name"], "Provider Template")
        self.assertEqual(defaults["saml_configuration"], saml_config)

    def test_create_or_update_provider_configuration_updates_existing(self):
        """
        Test updating an existing SAMLProviderConfig instance.

        Expected behavior:
            - Returns the existing instance with updated fields.
            - Calls `update_or_create` with `site`, `slug`, and updated values.
        """
        mock_manager = tpa_models.SAMLProviderConfig.objects.current_set.return_value
        mock_instance = Mock()
        mock_manager.update_or_create.return_value = (mock_instance, False)
        site = Site(domain="edu.org", name="Edu Site")
        slug = "edu-lms-sso"
        saml_config = Mock()
        template = SAMLBulkTemplateConfiguration(
            name="EduConfig",
            other_settings='{}'
        )

        result = template._create_or_update_provider_configuration(  # pylint: disable=protected-access
            site,
            slug,
            saml_config,
        )

        self.assertEqual(result, mock_instance)
        mock_manager.update_or_create.assert_called_once()

    @patch.object(SAMLBulkTemplateConfiguration, "_create_or_update_provider_configuration")
    @patch.object(SAMLBulkTemplateConfiguration, "_create_or_update_saml_configuration")
    def test_apply_to_sites_creates_expected_configurations(
        self, mock_create_saml, mock_create_provider
    ):
        """
        Test that `apply_to_sites` creates/upserts both SAMLConfiguration and SAMLProviderConfig
        for all sites passed.

        Expected behavior:
            - `_create_or_update_saml_configuration` is called for each site with the correct slug.
            - `_create_or_update_provider_configuration` is called for each site with the correct slug and config.
        """
        template = SAMLBulkTemplateConfiguration(name="Example Template")
        site1 = Site(domain="bc.futurex.sa", name="Site 1")
        site2 = Site(domain="abc.example.sa", name="Site 2")
        mock_config_1 = Mock()
        mock_config_2 = Mock()
        mock_create_saml.side_effect = [mock_config_1, mock_config_2]

        template.apply_to_sites([site1, site2])

        mock_create_saml.assert_has_calls([
            call(site1, "bc-futurex-lms-sso"),
            call(site2, "abc-example-lms-sso"),
        ])
        mock_create_provider.assert_has_calls([
            call(site1, "bc-futurex-lms-sso", mock_config_1),
            call(site2, "abc-example-lms-sso", mock_config_2),
        ])

    @patch.object(SAMLBulkTemplateConfiguration, "apply_to_sites")
    def test_save_calls_super_and_apply_to_sites(self, mock_apply):
        """
        Test the overridden `save` method.

        Expected behavior:
            - Calls `apply_to_sites` with all related sites.
        """
        site1 = Site.objects.create(domain="bc.futurex.sa", name="Site 1")
        site2 = Site.objects.create(domain="abc.example.sa", name="Site 2")
        template = SAMLBulkTemplateConfiguration.objects.create(  # pylint: disable=no-member
            name="Example Template",
            identity_provider_type="Standard SAML provider",
        )
        template.sites.add(site1, site2)
        mock_apply.reset_mock()

        template.save()

        mock_apply.assert_called_once_with([site2, site1])

    def test_str_returns_formatted_representation(self):
        """
        Test the string representation of the SAMLBulkTemplateConfiguration instance.

        Expected behavior:
            - Returns a string in the format: "SAMLBulkTemplateConfiguration <name> with id <id>"
        """
        template = SAMLBulkTemplateConfiguration(name="Test Template")
        expected = f"SAMLBulkTemplateConfiguration {template.name} with id {template.id}"  # pylint: disable=no-member

        self.assertEqual(str(template), expected)
