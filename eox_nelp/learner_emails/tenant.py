"""Bind a Celery worker to the tenant of a course, so the e-mail is branded with ITS values."""
from urllib.parse import urlparse

from django.conf import settings
from eox_tenant.constants import LMS_CONFIG_COLUMN
from eox_tenant.signals import _update_settings, can_keep_settings

from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers


class TenantNotResolvedError(Exception):
    """The tenant of a course could not be bound; sending would mean an unbranded e-mail."""


def tenant_root_url(org):
    """Return the LMS root URL of the tenant that owns the org (the global one if it sets none)."""
    return configuration_helpers.get_value_for_org(org, "LMS_ROOT_URL", settings.LMS_ROOT_URL)


def tenant_domain_for_org(org):
    """Return the domain of the tenant that owns the org (the host of its LMS root URL).

    The certificate link is built from the same root URL, so branding and link always agree.
    """
    return urlparse(tenant_root_url(org)).hostname


def bind_tenant_for_org(org):
    """Make `django.conf.settings` carry the tenant values (logo, name, ...) of the org.

    A worker has no request, so nothing binds the tenant for us unless the task was queued from
    a tenant request. If the tenant cannot be bound we FAIL instead of sending an unbranded mail.

    Returns:
        str: The bound tenant domain.

    Raises:
        TenantNotResolvedError: When the domain is unknown or eox-tenant did not bind it.
    """
    domain = tenant_domain_for_org(org)

    if not domain:
        raise TenantNotResolvedError(f"No tenant domain for org={org}")

    if not can_keep_settings(domain):  # also resets what a previous tenant left in settings
        _update_settings(domain, LMS_CONFIG_COLUMN)

    if getattr(settings, "EDNX_TENANT_DOMAIN", None) != domain:
        raise TenantNotResolvedError(f"Tenant {domain} (org={org}) could not be bound")

    return domain
