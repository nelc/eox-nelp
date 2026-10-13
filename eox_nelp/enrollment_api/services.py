"""Enrollment rules of the eox-nelp override, testable without HTTP.

One item in, one response-item list out (the shape eox-core's `single_enrollment_create` returns,
plus `result`). Decisions: ADR 0001 (reserve unknown emails), 0002 (`result` + status), 0004 (mail
queued after commit), 0007 (existing account of another tenant is enrolled directly).
"""
import logging
import time
from dataclasses import dataclass

from django.db import transaction
from eox_core.edxapp_wrapper.coursekey import get_valid_course_key
from rest_framework.exceptions import APIException, NotFound, ValidationError

from eox_nelp.edxapp_wrapper.enrollment_api import (
    account_exists,
    enroll_email,
    get_course_overview,
    is_actively_enrolled,
    user_on_site,
)
from eox_nelp.enrollment_api.audit import log_event, user_ref
from eox_nelp.enrollment_api.tasks import send_enrollment_mail

logger = logging.getLogger("eox_nelp.enrollment_api")

ENROLLED = "enrolled"
RESERVED = "reserved"
NOTICE = "notice"          # mail to an existing account: ace `enrolled_enroll`
INVITATION = "invitation"  # mail to a reserved email: ace `allowed_enroll`
MESSAGE_TYPE = {NOTICE: "enrolled_enroll", INVITATION: "allowed_enroll"}


class EnrollmentClosed(APIException):
    """The course does not accept enrollments now (closed window or ended)."""

    status_code = 400
    default_detail = "Enrollment closed"
    default_code = "enrollment_closed"


@dataclass(frozen=True)
class CallContext:
    """What the view knows about the call; copied into logs and into the queued mail."""

    request_id: str
    caller_app: str
    site_id: int
    site_domain: str


class EnrollmentService:
    """Enrol or reserve one item.

    Args:
        ctx: CallContext of the request.
        find_user: callable(item) -> user, raising NotFound when no account matches.
        enroll_account: callable(**item) -> list of response dicts (eox-core's create path).
    """

    def __init__(self, ctx, find_user, enroll_account):
        self.ctx = ctx
        self.find_user = find_user
        self.enroll_account = enroll_account

    def enroll(self, item, batch_index):
        """Process one item; log its `enrollment_api_result` event; re-raise APIExceptions as item errors."""
        fields = {
            "request_id": self.ctx.request_id, "course_id": item.get("course_id"), "mode": item.get("mode"),
            "caller_app": self.ctx.caller_app, "site": self.ctx.site_domain, "batch_index": batch_index,
            "user_ref": user_ref(item["email"]) if item.get("email") else None,
        }
        started = time.monotonic()
        try:
            data, outcome, template = self._process(item, fields)
        except APIException as exc:
            log_event(**fields, outcome="rejected", reason=type(exc).__name__, level=logging.WARNING)
            raise
        except Exception:
            logger.exception("enrollment_api_result unexpected error request_id=%s", self.ctx.request_id)
            raise
        log_event(
            **fields, outcome=outcome, email_template=template, email_attempted="true" if template else "false",
            email_result="queued" if template else None, email_ms=round((time.monotonic() - started) * 1000),
        )
        return data

    # -- one item ---------------------------------------------------------------------------

    def _process(self, item, fields):
        """Return (response items, outcome, mail template or None)."""
        if item.get("bundle_id"):  # program enrolment: untouched eox-core behaviour, no mail
            return self.enroll_account(**item), ENROLLED, None
        course_key = get_valid_course_key(item["course_id"])
        if not item.get("force"):
            self._ensure_open(course_key)
        try:
            user = self.find_user(item)
        except NotFound:
            # Reserve only for an email nobody owns; a username, or an account the lookup
            # filtered out, keeps the plain "not found" error it has today.
            if item.get("username") or not item.get("email") or account_exists(item["email"]):
                raise
            return self._reserve(item, course_key, fields)
        return self._enroll_existing(user, item, course_key, fields)

    @staticmethod
    def _ensure_open(course_key):
        """Reject a course that is closed for enrollment or has ended (owner Q4)."""
        overview = get_course_overview(course_key)
        if not overview.is_enrollment_open() or overview.has_ended():
            raise EnrollmentClosed()

    def _reserve(self, item, course_key, fields):
        """Unknown email: keep a CourseEnrollmentAllowed (auto-enrol on registration), invite once."""
        email = item["email"].strip()
        before, after, _ = enroll_email(course_key, email, auto_enroll=True, message_students=False)
        if not after.allowed:
            raise ValidationError("This email cannot be enrolled.")  # e.g. a retired address
        data = [{"email": email, "course_id": str(course_key), "mode": item["mode"], "is_active": True,
                 "result": RESERVED}]
        template = self._queue_mail(INVITATION, email, course_key, fields, send=not before.allowed)
        return data, RESERVED, template

    def _enroll_existing(self, user, item, course_key, fields):
        """Account exists (any tenant): eox-core's own create path, then tag and maybe notify."""
        was_active = is_actively_enrolled(user, course_key)
        rows = self.enroll_account(**item)
        if any(row.get("messages") for row in rows):  # eox-core reported a validation problem: leave as is
            return rows, "rejected", None
        for row in rows:
            row["result"] = ENROLLED
        is_active = item.get("is_active", True)
        if not user_on_site(user, self.ctx.site_domain):
            outcome = "enrolled_cross_tenant"
        else:
            outcome = "already_enrolled" if was_active and is_active else ENROLLED
        notify = is_active and not was_active  # only a real state change sends mail
        return rows, outcome, self._queue_mail(NOTICE, user.email, course_key, fields, send=notify)

    def _queue_mail(self, template, email, course_key, fields, send):
        """After the transaction commits, queue the mail; returns the template used, None when no mail is due."""
        if not send:
            return None
        log_fields = {**fields, "user_ref": user_ref(email), "email_template": template}
        transaction.on_commit(lambda: send_enrollment_mail.delay(
            MESSAGE_TYPE[template], email, str(course_key), True, self.ctx.site_id, log_fields,
        ))
        return template
