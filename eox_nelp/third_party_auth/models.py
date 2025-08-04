"""
models.py - SAML Bulk Template Configuration

This module defines the SAMLBulkTemplateConfiguration model, which serves as a reusable
template for provisioning SAML-based authentication configurations across multiple Django sites.
It centralizes and automates the creation and synchronization of both SAMLConfiguration and
SAMLProviderConfig instances for all associated sites.

Key features:
- Provides a single source of truth for common SAML settings.
- Supports auto-provisioning and synchronization of third-party auth configurations on save.
- Uses ManyToMany relation with django.contrib.sites.models.Site to control scope.
- Includes helper methods to generate site-specific values such as slugs and organization metadata.
- Applies configuration updates both through model save and m2m_changed signals.

Intended use:
- Admins define and maintain reusable SAML configuration templates.
- Upon saving or adding a new site, the corresponding SAML configurations are created or updated automatically.

Related components:
- tpa_models.SAMLConfiguration
- tpa_models.SAMLProviderConfig

This model is meant to simplify enterprise SSO integration in multi-site Open edX deployments.
"""
import json

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import gettext_lazy as _

from eox_nelp.edxapp_wrapper.third_party_auth import models as tpa_models

User = get_user_model()


class SAMLBulkTemplateConfiguration(models.Model):
    """
    Template model to automate the creation of SAMLConfiguration and ProviderConfiguration
    instances by centralizing common field values.
    """
    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saml_bulk_templates_modified",
    )
    changed_date = models.DateTimeField(auto_now=True)
    sites = models.ManyToManyField(Site, related_name="saml_bulk_templates")
    slug_suffix = models.CharField(
        max_length=50,
        default="lms-sso",
        help_text=(
            "Suffix appended to the generated slug after removing the TLD. "
            "For example, with domain 'example.org' and suffix 'custom-idp', "
            "the slug becomes 'example-custom-idp'."
        ),
    )
    use_default_saml_configuration_slug = models.BooleanField(
        default=True,
        help_text=(
            "If checked, the slug for each site will be the default value defined in the model. "
            "If unchecked, a dynamic slug will be generated from the site domain and the `slug_suffix`."
        ),
    )

    # Common Provider fields
    icon_class = models.CharField(max_length=100, blank=True)
    icon_image = models.ImageField(upload_to="saml/icons/", blank=True, null=True)
    secondary = models.BooleanField(default=False)
    send_welcome_email = models.BooleanField(default=False)
    visible = models.BooleanField(default=True)
    max_session_length = models.PositiveIntegerField(null=True, blank=True)
    sync_learner_profile_data = models.BooleanField(default=True)
    enable_sso_id_verification = models.BooleanField(default=True)
    disable_for_enterprise_sso = models.BooleanField(default=False)
    backend_name = models.CharField(
        max_length=50,
        default='tpa-saml',
        blank=True,
        help_text="Which python-social-auth provider backend to use. 'tpa-saml' is the standard edX SAML backend."
    )
    entity_id = models.CharField(
        max_length=255,
        verbose_name="Entity ID",
        blank=True,
        help_text="Example: https://idp.testshib.org/idp/shibboleth"
    )
    metadata_source = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "URL to this provider's XML metadata. Should be an HTTPS URL. "
            "Example: https://www.testshib.org/metadata/testshib-providers.xml"
        )
    )
    attr_user_permanent_id = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="User ID Attribute",
        help_text=(
            "URN of the SAML attribute that we can use as a unique, "
            "persistent user ID. Leave blank for default."
        )
    )
    attr_full_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Full Name Attribute",
        help_text="URN of SAML attribute containing the user's full name. Leave blank for default."
    )
    default_full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Default Value for Full Name",
        help_text="Default value for full name to be used if not present in SAML response."
    )
    attr_first_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="First Name Attribute",
        help_text="URN of SAML attribute containing the user's first name. Leave blank for default."
    )
    default_first_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Default Value for First Name",
        help_text="Default value for first name to be used if not present in SAML response."
    )
    attr_last_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Last Name Attribute",
        help_text="URN of SAML attribute containing the user's last name. Leave blank for default."
    )
    default_last_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Default Value for Last Name",
        help_text="Default value for last name to be used if not present in SAML response.")
    attr_username = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Username Hint Attribute",
        help_text="URN of SAML attribute to use as a suggested username for this user. Leave blank for default."
    )
    default_username = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Default Value for Username",
        help_text="Default value for username to be used if not present in SAML response."
    )
    attr_email = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Email Attribute",
        help_text="URN of SAML attribute containing the user's email address[es]. Leave blank for default.")
    default_email = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Default Value for Email",
        help_text="Default value for email to be used if not present in SAML response."
    )
    automatic_refresh_enabled = models.BooleanField(
        default=True,
        verbose_name="Enable automatic metadata refresh",
        help_text="When checked, the SAML provider's metadata will be included "
                  "in the automatic refresh job, if configured."
    )
    identity_provider_type = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Identity Provider Type",
        default=tpa_models.STANDARD_SAML_PROVIDER_KEY,
        choices=tpa_models.get_saml_idp_choices(), help_text=(
            "Some SAML providers require special behavior. For example, SAP SuccessFactors SAML providers require an "
            "additional API call to retrieve user metadata not provided in the SAML response. Select the provider type "
            "which best matches your use case. If in doubt, choose the Standard SAML Provider type."
        )
    )
    country = models.CharField(
        max_length=128,
        help_text=(
            'URN of SAML attribute containing the user`s country.',
        ),
        blank=True,
    )
    skip_hinted_login_dialog = models.BooleanField(
        default=True,
        help_text=_(
            "If this option is enabled, users that visit a \"TPA hinted\" URL for this provider "
            "(e.g. a URL ending with `?tpa_hint=[provider_name]`) will be forwarded directly to "
            "the login URL of the provider instead of being first prompted with a login dialog."
        ),
    )
    skip_registration_form = models.BooleanField(
        default=True,
        help_text=_(
            "If this option is enabled, users will not be asked to confirm their details "
            "(name, email, etc.) during the registration process. Only select this option "
            "for trusted providers that are known to provide accurate user information."
        ),
    )
    skip_email_verification = models.BooleanField(
        default=True,
        help_text=_(
            "If this option is selected, users will not be required to confirm their "
            "email, and their account will be activated immediately upon registration."
        ),
    )
    send_to_registration_first = models.BooleanField(
        default=True,
        help_text=_(
            "If this option is selected, users will be directed to the registration page "
            "immediately after authenticating with the third party instead of the login page."
        ),
    )
    other_settings = models.TextField(
        verbose_name="Advanced settings", blank=True,
        help_text=(
            'For advanced use cases, enter a JSON object with addtional configuration. '
            'The tpa-saml backend supports {"requiredEntitlements": ["urn:..."]}, '
            'which can be used to require the presence of a specific eduPersonEntitlement, '
            'and {"extra_field_definitions": [{"name": "...", "urn": "..."},...]}, which can be '
            'used to define registration form fields and the URNs that can be used to retrieve '
            'the relevant values from the SAML response. Custom provider types, as selected '
            'in the "Identity Provider Type" field, may make use of the information stored '
            'in this field for additional configuration.'
        )
    )
    archived = models.BooleanField(default=False)

    # Common Configuration fields
    organization_info_template = models.TextField(
        verbose_name="Organization Info",
        default='{"en-US": {"url": "http://www.example.com", "displayname": "Example Inc.", "name": "example"}}',
        help_text="JSON dictionary of 'url', 'displayname', and 'name' for each language",
    )
    other_config_str = models.TextField(
        default='{\n"SECURITY_CONFIG": {"metadataCacheDuration": 604800, "signMetadata": false}\n}',
        help_text=(
            "JSON object defining advanced settings that are passed on to python-saml. "
            "Valid keys that can be set here include: SECURITY_CONFIG and SP_EXTRA"
        ),
    )

    def __str__(self):
        return f"SAMLBulkTemplateConfiguration {self.name} with id {self.id}"  # pylint: disable=no-member

    def generate_slug_for_site(self, site):
        """
        Generates a slug for the given Site instance based on its domain.
        Converts 'bc.futurex.sa' -> 'bc-futurex-lms-sso' (removing TLD).
        Falls back to full domain if no TLD is present.

        Args:
            site (Site): A Django Site instance.

        Returns:
            str: The generated slug.
        """
        domain_parts = site.domain.split('.')

        if len(domain_parts) > 1:
            base_parts = domain_parts[:-1]
        else:
            base_parts = domain_parts

        slug = '-'.join(base_parts)

        return f"{slug}-{self.slug_suffix}"

    def generate_configuration_entity_id_for_site(self, site):
        """
        Generates the configuration entity ID URL for the given Site instance.

        Example:
            For site.domain = 'bc.futurex.sa', returns 'https://saml.bc.futurex.sa'

        Args:
            site (Site): A Django Site instance.

        Returns:
            str: The generated configuration entity ID URL.
        """
        return f"https://saml.{site.domain}"

    def generate_organization_info_for_site(self, site):
        """
        Renders the organization_info by formatting the template with the given site's domain.

        Args:
            site (Site): A Django Site instance.

        Returns:
            str: Rendered organization_info as a JSON string.
        """
        domain = site.domain
        try:
            parsed = json.loads(self.organization_info_template)
        except json.JSONDecodeError:
            return self.organization_info_template  # fallback to raw if invalid

        formatted = {
            lang: {
                key: value.format(domain=domain)
                for key, value in data.items()
            }
            for lang, data in parsed.items()
        }

        return json.dumps(formatted, indent=2)

    def _create_or_update_saml_configuration(self, site, slug):
        """
        Create or update the SAMLConfiguration for a specific site.
        """
        if self.use_default_saml_configuration_slug:
            slug = "default"

        defaults = {
            "enabled": True,
            "changed_by": self.changed_by,
            "entity_id": self.generate_configuration_entity_id_for_site(site),
            "org_info_str": self.generate_organization_info_for_site(site),
            "other_config_str": self.other_config_str,
            "is_public": True,
        }

        saml_config, _ = tpa_models.SAMLConfiguration.objects.current_set().update_or_create(
            site=site,
            slug=slug,
            defaults=defaults,
        )
        return saml_config

    def _create_or_update_provider_configuration(self, site, slug, saml_config):
        """
        Create or update the ProviderConfiguration for a specific site.
        """
        defaults = {
            "enabled": True,
            "name": self.name,
            "changed_by": self.changed_by,
            "icon_class": self.icon_class,
            "icon_image": self.icon_image,
            "secondary": self.secondary,
            "send_welcome_email": self.send_welcome_email,
            "visible": self.visible,
            "max_session_length": self.max_session_length,
            "sync_learner_profile_data": self.sync_learner_profile_data,
            "enable_sso_id_verification": self.enable_sso_id_verification,
            "disable_for_enterprise_sso": self.disable_for_enterprise_sso,
            "backend_name": self.backend_name,
            "entity_id": self.entity_id,
            "metadata_source": self.metadata_source,
            "attr_user_permanent_id": self.attr_user_permanent_id,
            "attr_full_name": self.attr_full_name,
            "default_full_name": self.default_full_name,
            "attr_first_name": self.attr_first_name,
            "default_first_name": self.default_first_name,
            "attr_last_name": self.attr_last_name,
            "default_last_name": self.default_last_name,
            "attr_username": self.attr_username,
            "default_username": self.default_username,
            "attr_email": self.attr_email,
            "default_email": self.default_email,
            "automatic_refresh_enabled": self.automatic_refresh_enabled,
            "identity_provider_type": self.identity_provider_type,
            "country": self.country,
            "skip_hinted_login_dialog": self.skip_hinted_login_dialog,
            "skip_registration_form": self.skip_registration_form,
            "skip_email_verification": self.skip_email_verification,
            "send_to_registration_first": self.send_to_registration_first,
            "other_settings": self.other_settings,
            "archived": self.archived,
            "saml_configuration": saml_config,
        }

        saml_provider_config, _ = tpa_models.SAMLProviderConfig.objects.current_set().update_or_create(
            site=site,
            archived=False,
            slug=slug,
            defaults=defaults,
        )

        return saml_provider_config

    def apply_to_sites(self, sites):
        """
        Creates or updates ProviderConfiguration and SAMLConfiguration instances
        for each site associated with this template.
        """
        for site in sites:
            slug = self.generate_slug_for_site(site)

            saml_config = self._create_or_update_saml_configuration(site, slug)
            self._create_or_update_provider_configuration(site, slug, saml_config)

    def save(self, *args, **kwargs):
        """
        Overrides the default save method to automatically apply the configuration
        to all related sites after saving the template.
        """
        super().save(*args, **kwargs)
        self.apply_to_sites(list(self.sites.all()))  # pylint: disable=no-member
