"""Wrapper with the edx-platform / edx-ace pieces the learner e-mails need.

Attributes:
    backend: Imported module by using the plugin settings.
    BaseMessageType: Platform base class of the ace messages (adds the tenant from-address).
    send_and_confirm: Send an ace message and say whether the delivery really happened.
    make_recipient: Ace recipient of a user.
    emulate_tenant_request: Context manager: a fake request on the tenant Site and with the tenant theme.
    get_site_for_domain: Site row of a tenant domain.
    get_base_context: Template context every ace frame expects (logo, platform name, ...).
    get_user_language: Language the learner saved in the account settings, or None.
    get_downloadable_certificate: The learner's downloadable certificate of a course, or None.
    get_certificate_url: Path of the certificate page.
    iter_downloadable_certificates: (user_id, course_id) of every downloadable certificate of an org.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_LEARNER_EMAILS_BACKEND)

BaseMessageType = backend.BaseMessageType
send_and_confirm = backend.send_and_confirm
make_recipient = backend.make_recipient
emulate_tenant_request = backend.emulate_tenant_request
get_site_for_domain = backend.get_site_for_domain
get_base_context = backend.get_base_context
get_user_language = backend.get_user_language
get_downloadable_certificate = backend.get_downloadable_certificate
get_certificate_url = backend.get_certificate_url
iter_downloadable_certificates = backend.iter_downloadable_certificates
