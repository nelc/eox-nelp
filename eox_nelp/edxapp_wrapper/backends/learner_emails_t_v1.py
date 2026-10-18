"""Backend with the edx-platform / edx-ace pieces the learner e-mails use (Teak).

Sources (edx-platform, open-release/teak.nelp):
  openedx/core/djangoapps/ace_common/message.py, template_context.py: BaseMessageType, get_base_template_context
  openedx/core/lib/celery/task_utils.py: emulate_http_request
  lms/djangoapps/certificates/{models,utils}.py: GeneratedCertificate, get_certificate_url
"""
# pylint: disable=import-error
from contextlib import contextmanager

from common.djangoapps.student.models import CourseEnrollment
from crum import CurrentRequestUserMiddleware, get_current_request
from django.contrib.sites.models import Site
from django.urls import reverse
from edx_ace import ace
from edx_ace.recipient import Recipient
from edx_ace.signals import ACE_MESSAGE_SENT
from eox_tenant.tenant_wise.proxies import TenantSiteConfigProxy
from lms.djangoapps.certificates.data import CertificateStatuses
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.certificates.utils import get_certificate_url  # noqa: F401
from openedx.core.djangoapps.ace_common.message import BaseMessageType  # noqa: F401
from openedx.core.djangoapps.ace_common.template_context import \
    get_base_template_context as get_base_context  # noqa: F401, E501
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.user_api.models import UserPreference
from openedx.core.lib.celery.task_utils import emulate_http_request


def send_and_confirm(message):
    """Send the ace message and return True only if ace reports it delivered.

    `ace.send` swallows template and channel errors (it only reports them to monitoring), so the
    only reliable "it went out" signal is ACE_MESSAGE_SENT, matched here on the message uuid.
    """
    delivered = []

    def _on_sent(sender, message, **kwargs):  # pylint: disable=unused-argument
        delivered.append(message["uuid"])

    ACE_MESSAGE_SENT.connect(_on_sent, weak=False)
    try:
        ace.send(message)
    finally:
        ACE_MESSAGE_SENT.disconnect(_on_sent)

    return str(message.uuid) in delivered


def make_recipient(user):
    """Ace recipient of the user."""
    return Recipient(lms_user_id=user.id, email_address=user.email)


def get_site_for_domain(domain):
    """Site of the tenant domain; raises Site.DoesNotExist (the e-mail needs the right host)."""
    return Site.objects.get(domain=domain)


@contextmanager
def emulate_tenant_request(site, user):
    """Fake request for a Celery worker: the tenant Site and the tenant's OWN theme.

    The stock middleware resolves the theme from the Site's SiteTheme row (one global theme). The
    eox-theming one resolves it from the tenant settings, so the caller must bind the tenant FIRST.
    """
    # Imported here, not at module level: this module loads with the signal receivers in Studio
    # too, and eox-theming's middleware reads LMS-only settings when it is imported.
    from eox_theming.theming.middleware import EoxThemeMiddleware  # pylint: disable=import-outside-toplevel

    site.configuration = TenantSiteConfigProxy()  # what eox-tenant sets on a real request
    with emulate_http_request(
        site=site, user=user, middleware_classes=[CurrentRequestUserMiddleware, EoxThemeMiddleware],
    ):
        if not hasattr(get_current_request(), "site_theme"):
            raise RuntimeError("The tenant theme could not be resolved for the e-mail")
        yield


def get_user_language(user):
    """Language the learner saved in the account settings, or None."""
    return UserPreference.get_value(user, "pref-lang")


def get_downloadable_certificate(user_id, course_key):
    """The learner's downloadable certificate for the course, or None."""
    return GeneratedCertificate.objects.filter(
        user_id=user_id, course_id=course_key, status=CertificateStatuses.downloadable,
    ).first()


def iter_downloadable_certificates(org):
    """Yield (user_id, course_id) of every downloadable certificate of the org's courses."""
    course_ids = CourseOverview.objects.filter(org=org).values_list("id", flat=True)
    certificates = GeneratedCertificate.objects.filter(
        course_id__in=list(course_ids), status=CertificateStatuses.downloadable,
    ).values_list("user_id", "course_id")

    for user_id, course_id in certificates.iterator(chunk_size=2000):
        yield user_id, str(course_id)


def _course_rows(queryset):
    """(course_id, org, start, end) of the overviews, as plain tuples (no ORM objects leave the backend)."""
    return [(str(c.id), c.org, c.start, c.end) for c in queryset.only("id", "org", "start", "end")]


def list_orgs():
    """Every org that has at least one course."""
    return list(CourseOverview.objects.values_list("org", flat=True).distinct())


def find_started_courses(org, since, until):
    """Courses of the org whose start is in [since, until]."""
    return _course_rows(CourseOverview.objects.filter(org=org, start__gte=since, start__lte=until))


def find_courses_ending(org, since, until):
    """Courses of the org whose end is in [since, until]."""
    return _course_rows(CourseOverview.objects.filter(org=org, end__gte=since, end__lte=until))


def find_running_courses(org, now):
    """Courses of the org that have started and have not ended."""
    started = CourseOverview.objects.filter(org=org, start__lte=now)
    return _course_rows(started.filter(end__isnull=True) | started.filter(end__gt=now))


def iter_enrollments(course_id):
    """(user_id, created) of the ACTIVE enrollments of the course, streamed."""
    rows = CourseEnrollment.objects.filter(course_id=course_id, is_active=True, user__is_active=True)
    return rows.values_list("user_id", "created").iterator(chunk_size=2000)


def _aggregator():
    """The completion-aggregator model, imported on use.

    Not a module-level import: the LMS loads this module at startup (to register the e-mail tasks)
    and openedx-completion-aggregator is not installed everywhere (e.g. the Tutor integration
    stacks). Where it is missing, only the progress reminder fails, loudly, when it runs.
    """
    from completion_aggregator.models import Aggregator  # pylint: disable=import-outside-toplevel
    return Aggregator


def iter_progress(course_id, min_percent):
    """(user_id, percent) of the course-level completion rows at or over `min_percent`, streamed.

    Uses the (course_key, aggregation_name, ...) index of the aggregator table; the aggregate is
    refreshed hourly by `run_aggregator_service`, so the number is up to about an hour old.
    """
    rows = _aggregator().objects.filter(course_key=course_id, aggregation_name="course", percent__gte=min_percent)
    return rows.values_list("user_id", "percent").iterator(chunk_size=2000)


def get_progress(user_id, course_id):
    """The learner's course completion (0..1); 0 when the aggregate has no row for them yet."""
    percent = _aggregator().objects.filter(
        user_id=user_id, course_key=course_id, aggregation_name="course",
    ).values_list("percent", flat=True).first()
    return percent or 0.0


def is_enrolled(user_id, course_id):
    """True when the learner has an active enrollment in the course."""
    return CourseEnrollment.objects.filter(user_id=user_id, course_id=course_id, is_active=True).exists()


def has_certificate(user_id, course_id):
    """True when the learner already holds a downloadable certificate for the course."""
    return GeneratedCertificate.objects.filter(
        user_id=user_id, course_id=course_id, status=CertificateStatuses.downloadable,
    ).exists()


def get_course_path(course_id):
    """Path of the course home page."""
    return reverse("course_root", kwargs={"course_id": str(course_id)})
