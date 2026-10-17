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
    get_course_path,
    get_downloadable_certificate,
    get_progress,
    get_site_for_domain,
    get_user_language,
    has_certificate,
    is_enrolled,
    make_recipient,
    send_and_confirm,
)
from eox_nelp.learner_emails.journey import progress_due, reminder_thresholds
from eox_nelp.learner_emails.language import resolve_language
from eox_nelp.learner_emails.messages import CertificateReady, CompletionReminder, LearningStarts
from eox_nelp.learner_emails.models import CERTIFICATE_READY, LEARNING_STARTS, REMINDER_PROGRESS, LearnerEmailLog
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


def _certificate_extras(user, certificate, org):
    """Template context of the certificate-ready e-mail beyond the common keys."""
    root = tenant_root_url(org).rstrip("/")
    path = get_certificate_url(user_id=user.id, course_id=certificate.course_id, uuid=certificate.verify_uuid)

    if not path:
        raise ValueError("The certificate has no page to link to")

    return {"certificate_url": f"{root}/{path.lstrip('/')}"}


def _course_url(course_key):
    """Course home page on the tenant of the (already bound) course org."""
    return f"{tenant_root_url(course_key.org).rstrip('/')}/{get_course_path(course_key).lstrip('/')}"


def _deliver(kind, message_class, user_id, course_id, prepare):
    """Send one learner e-mail once; raise on any failure so the caller can retry.

    The tenant is bound first (branding, flags, theme), `prepare(user, course_key)` decides whether
    there is anything to send (None = skip) and returns the message-specific context, then the log
    row is claimed and the mail sent. If the send fails the claim is released so a retry can take it.
    """
    course_key = CourseKey.from_string(course_id)
    domain = bind_tenant_for_org(course_key.org)
    site = get_site_for_domain(domain)
    user = User.objects.select_related("profile").get(id=user_id)
    extras = prepare(user, course_key)

    if extras is None:
        logger.info("%s skipped, nothing to send user_id=%s course_id=%s", kind, user_id, course_id)
        return

    if not _claim(user_id, course_id, kind):
        return

    try:
        overview = get_course_overview(course_key)
        language = resolve_language(overview.language, get_user_language(user))
        context = {
            "full_name": user.profile.name,  # may be blank: the templates then greet without a name
            "course_name": overview.display_name,
            "course_id": str(course_key),  # NOT `course_ids`: that key triggers the bulk-email opt-out policy
            **extras,
        }
        with emulate_tenant_request(site, user):
            context = {**get_base_context(site), **context}
            message = message_class().personalize(make_recipient(user), language, context)
            if not send_and_confirm(message):
                raise EmailNotDeliveredError("ACE did not report the delivery")
    except Exception:
        LearnerEmailLog.objects.filter(  # pylint: disable=no-member
            user_id=user_id, course_id=course_id, kind=kind,
        ).delete()
        raise

    logger.info("%s sent user_id=%s course_id=%s language=%s", kind, user_id, course_id, language)


def deliver_certificate_ready(user_id, course_id):
    """Send the certificate-ready e-mail once (a revoked certificate is not announced)."""
    def prepare(user, course_key):
        certificate = get_downloadable_certificate(user.id, course_key)
        return None if certificate is None else _certificate_extras(user, certificate, course_key.org)

    _deliver(CERTIFICATE_READY, CertificateReady, user_id, course_id, prepare)


def deliver_learning_starts(user_id, course_id):
    """Send Message 3 once; a learner who unenrolled since the command picked them gets nothing."""
    def prepare(user, course_key):
        return {"course_url": _course_url(course_key)} if is_enrolled(user.id, course_key) else None

    _deliver(LEARNING_STARTS, LearningStarts, user_id, course_id, prepare)


def deliver_completion_reminder(user_id, course_id, kind):
    """Send Message 5 once per `kind` (REMINDER_PROGRESS or REMINDER_END) with the learner's actual progress.

    Everything is re-checked here (the command's list may be an hour old): still enrolled, no
    certificate yet, not complete, and for the progress kind still at or over the tenant threshold.
    """
    def prepare(user, course_key):
        percent = get_progress(user.id, course_key)
        threshold, _window = reminder_thresholds(course_key.org)
        due = progress_due(percent, threshold) if kind == REMINDER_PROGRESS else percent < 1
        if not due or not is_enrolled(user.id, course_key) or has_certificate(user.id, course_key):
            return None
        completed = int(round(percent * 100, 6))  # whole percent, rounded down
        return {"completed_percent": completed, "remaining_percent": 100 - completed,
                "course_url": _course_url(course_key)}

    _deliver(kind, CompletionReminder, user_id, course_id, prepare)


def _run(task, event, deliver, user_id, course_id):
    """Run `deliver`; retry transient failures; on the final failure log the alert line `<event>_failed`.

    The ERROR line is what the alert watches. There is no substitute path: a failed mail is
    reported, not replaced by another behaviour. Failures are logged by exception CLASS only,
    because SMTP errors carry the recipient address.
    """
    try:
        deliver()
    except Exception as exc:  # pylint: disable=broad-except
        attempt = task.request.retries
        if attempt < task.max_retries:
            error = RuntimeError(type(exc).__name__)
            raise task.retry(exc=error, countdown=RETRY_BASE_SECONDS * 2 ** attempt) from None
        logger.error("%s_failed user_id=%s course_id=%s error=%s", event, user_id, course_id, type(exc).__name__)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def send_certificate_ready_email(self, user_id, course_id):
    """Send the certificate-ready e-mail (queued by the CERTIFICATE_CREATED receiver)."""
    _run(self, "certificate_ready_email", lambda: deliver_certificate_ready(user_id, course_id), user_id, course_id)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def send_learning_starts_email(self, user_id, course_id):
    """Send Message 3, "learning starts" (queued by the send_journey_emails command)."""
    _run(self, "learning_starts_email", lambda: deliver_learning_starts(user_id, course_id), user_id, course_id)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def send_completion_reminder_email(self, user_id, course_id, kind):
    """Send Message 5, "completion reminder", for the trigger `kind` (queued by the send_journey_emails command)."""
    _run(self, "completion_reminder_email", lambda: deliver_completion_reminder(user_id, course_id, kind),
         user_id, course_id)
