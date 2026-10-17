"""Celery tasks that send the learner e-mails."""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from opaque_keys.edx.keys import CourseKey

from eox_nelp.edxapp_wrapper.enrollment_api import get_course_overview
from eox_nelp.edxapp_wrapper.learner_emails import (
    emulate_tenant_request,
    get_base_context,
    get_certificate_url,
    get_downloadable_certificate,
    get_site_for_domain,
    get_user_language,
    make_recipient,
    send_and_confirm,
)
from eox_nelp.learner_emails.language import resolve_language
from eox_nelp.learner_emails.messages import CertificateReady
from eox_nelp.learner_emails.models import CERTIFICATE_READY, LearnerEmailLog
from eox_nelp.learner_emails.tenant import bind_tenant_for_org, tenant_root_url

logger = logging.getLogger(__name__)
User = get_user_model()

MAX_RETRIES = 3
RETRY_BASE_SECONDS = 60  # 60s, 120s, 240s between attempts


class EmailNotDeliveredError(Exception):
    """ACE did not report the e-mail as delivered."""


def _claim(user_id, course_id, kind):
    """Insert the log row; False if it already exists (the learner already has, or is getting, the mail)."""
    try:
        with transaction.atomic():
            LearnerEmailLog.objects.create(user_id=user_id, course_id=course_id, kind=kind)  # pylint: disable=no-member
    except IntegrityError:
        return False

    return True


def _certificate_context(user, certificate, overview, org):
    """Template context of the certificate-ready e-mail (ids and names only, no raw e-mail)."""
    root = tenant_root_url(org).rstrip("/")
    path = get_certificate_url(user_id=user.id, course_id=certificate.course_id, uuid=certificate.verify_uuid)

    if not path:
        raise ValueError("The certificate has no page to link to")

    return {
        "full_name": user.profile.name,
        "course_name": overview.display_name,
        "certificate_url": f"{root}/{path.lstrip('/')}",
        "course_id": str(certificate.course_id),  # NOT `course_ids`: that key triggers the bulk-email opt-out policy
    }


def deliver_certificate_ready(user_id, course_id):
    """Send the certificate-ready e-mail once; raise on any failure so the caller can retry.

    The tenant is bound first (branding, flags, theme), then the log row is claimed, then the mail
    is sent. If the send fails the claim is released so the retry can take it again.
    """
    course_key = CourseKey.from_string(course_id)
    domain = bind_tenant_for_org(course_key.org)
    site = get_site_for_domain(domain)
    user = User.objects.select_related("profile").get(id=user_id)
    certificate = get_downloadable_certificate(user_id, course_key)

    if certificate is None:  # revoked or not passing any more: nothing to announce
        logger.info("certificate_ready_email skipped, no downloadable certificate user_id=%s course_id=%s",
                    user_id, course_id)
        return

    if not user.profile.name:
        raise ValueError("The learner has no name for the greeting")

    if not _claim(user_id, course_id, CERTIFICATE_READY):
        return

    try:
        overview = get_course_overview(course_key)
        language = resolve_language(overview.language, get_user_language(user))
        context = _certificate_context(user, certificate, overview, course_key.org)
        with emulate_tenant_request(site, user):
            context = {**get_base_context(site), **context}
            message = CertificateReady().personalize(make_recipient(user), language, context)
            if not send_and_confirm(message):
                raise EmailNotDeliveredError("ACE did not report the delivery")
    except Exception:
        LearnerEmailLog.objects.filter(  # pylint: disable=no-member
            user_id=user_id, course_id=course_id, kind=CERTIFICATE_READY,
        ).delete()
        raise

    logger.info("certificate_ready_email sent user_id=%s course_id=%s language=%s", user_id, course_id, language)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def send_certificate_ready_email(self, user_id, course_id):
    """Send the certificate-ready e-mail; retry transient failures; on the final failure log an ERROR.

    The ERROR line (`certificate_ready_email_failed`) is what the alert watches. There is no
    substitute path: a failed mail is reported, not replaced by another behaviour. Failures are
    logged by exception CLASS only, because SMTP errors carry the recipient address.
    """
    try:
        deliver_certificate_ready(user_id, course_id)
    except Exception as exc:  # pylint: disable=broad-except
        attempt = self.request.retries
        if attempt < self.max_retries:
            error = RuntimeError(type(exc).__name__)
            raise self.retry(exc=error, countdown=RETRY_BASE_SECONDS * 2 ** attempt) from None
        logger.error("certificate_ready_email_failed user_id=%s course_id=%s error=%s",
                     user_id, course_id, type(exc).__name__)
