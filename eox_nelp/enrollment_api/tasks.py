"""Celery task that sends the enrollment notice / invitation queued by the enrollment API.

The edx-platform helpers it calls run here, in a worker with no request, so the task rebuilds the
caller's context: the Site travels as an id and the work runs inside `emulate_http_request`.
(eox-tenant additionally stamps the published task with the caller's tenant domain, which the
worker binds before the task starts; that part is platform behaviour, not code of ours.)
"""
import logging
import time

from celery import shared_task
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from eox_nelp.edxapp_wrapper.enrollment_api import (
    emulate_http_request,
    get_course_overview,
    get_email_params,
    send_mail_to_student,
)
from eox_nelp.enrollment_api.audit import log_event

MAIL_MAX_RETRIES = 3
RETRY_BASE_SECONDS = 60  # 60s, 120s, 240s between attempts


def deliver(message_type, email, course_id, auto_enroll, site_id):
    """Render and send one ace enrollment message as the caller's site would."""
    site = Site.objects.get(id=site_id)
    user = get_user_model().objects.filter(email=email).first()
    with emulate_http_request(site=site, user=user):
        overview = get_course_overview(course_id)
        params = get_email_params(overview, auto_enroll, course_key=str(course_id))
        params.update({"message_type": message_type, "email_address": email})
        if message_type == "enrolled_enroll" and user:
            params["user_id"] = user.id
            params["full_name"] = getattr(getattr(user, "profile", None), "name", None)
        send_mail_to_student(email, params)


@shared_task(bind=True, max_retries=MAIL_MAX_RETRIES)
def send_enrollment_mail(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    self, message_type, email, course_id, auto_enroll, site_id, log_fields,
):
    """Send the mail; retry transient failures; on the final failure log it and let the enrolment stand.

    `log_fields` are the `enrollment_api_result` fields of the item (request_id, user_ref ...), so
    the delivery event can be joined to it. Failures are reported by exception CLASS only: SMTP
    errors carry the recipient address in their text, and Celery would copy it into its own log.
    """
    started = time.monotonic()
    try:
        deliver(message_type, email, course_id, auto_enroll, site_id)
    except Exception as exc:  # pylint: disable=broad-except
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=RuntimeError(type(exc).__name__),
                countdown=RETRY_BASE_SECONDS * 2 ** self.request.retries,
            ) from None
        log_event(
            "enrollment_api_email_result", logging.WARNING, **log_fields, email_attempted="true",
            email_result=f"failed:{type(exc).__name__}", email_ms=round((time.monotonic() - started) * 1000),
        )
        return
    log_event(
        "enrollment_api_email_result", logging.INFO, **log_fields, email_attempted="true",
        email_result="sent", email_ms=round((time.monotonic() - started) * 1000),
    )
