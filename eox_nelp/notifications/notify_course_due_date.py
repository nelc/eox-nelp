"""Notify course date module. This manage the delivery of an
upcoming_course_due_date
"""
import logging

from django.conf import settings
from django.utils import timezone
from edx_django_utils.db.read_replica import use_read_replica_if_available

from eox_nelp.edxapp_wrapper.bulk_email import CourseEmailTemplate, get_course_email_context
from eox_nelp.edxapp_wrapper.student import CourseEnrollment
from eox_nelp.notifications.utils import (
    get_xblock_course_from_usage_key_string,
    get_xblock_from_usage_key_string,
    send_email_multialternative,
)

logger = logging.getLogger(__name__)


def notify_upcoming_course_due_date(upcoming_course_due_date):
    """Send the correspongind email of an UpcomingCourseDate object.
    This is using the bulk-email template that already exists.
    Args:
        upcoming_course_due_date (UpcomingCourseDate): UpcomingCourseDate object to sent emails.
    """
    subsection_key_string = str(upcoming_course_due_date.location_id)
    enrollments_qs = use_read_replica_if_available(
        CourseEnrollment.objects.filter(course__id=upcoming_course_due_date.course_id, is_active=True),
    )
    recipient_emails = [enrollment.user.email for enrollment in enrollments_qs if enrollment.user.email]

    subsection_xblock = get_xblock_from_usage_key_string(subsection_key_string)
    course_xblock = get_xblock_course_from_usage_key_string(subsection_key_string)

    if not (subsection_xblock and recipient_emails and course_xblock):
        logger.info(
            "is missing one of the following: subsection-xblock(%s),recipient_emails(%s),course_xblock(%s)",
            subsection_xblock, recipient_emails, course_xblock
        )
        return

    rendered_email_msgs = generate_email_messages(subsection_xblock, course_xblock)
    # to do, add tenant aware settings for context and particular course notification template.

    sent = send_email_multialternative(**rendered_email_msgs, recipient_emails=recipient_emails)

    if sent:
        upcoming_course_due_date.sent = True
        upcoming_course_due_date.save()
        logger.info(
            "%s emails sent related the upcoming_course_due_date: %s -------",
            sent,
            upcoming_course_due_date.__dict__,
        )
    else:
        logger.info(
            "------- No emails were sent!!!, the email function returned %s -------",
            sent,
        )


def generate_email_messages(subsection_xblock, course_xblock):
    """Generate the messages of the email with the data of the subsection and
    course xblock. Return  a dict with the the keys subject, plaintext_msg and html_msg
    of the email to sent.

        Args:
            subsection_xblock (subsectionXblock)
            course_xblock (courseXblock)

        Returns:
            (dict): Dict with the messages rendered of the email.
            It contains: subject, plaintext_msg and html_msg
    """
    course_email_template = CourseEmailTemplate.get_template(name='base-notification-template')
    email_context = get_course_email_context(course_xblock)
    email_context["subsection_title"] = subsection_xblock.display_name
    email_context["subsection_delta"] = subsection_xblock.due - timezone.now()
    email_context["subsection_due_date"] = subsection_xblock.due

    return {
        "subject": settings.FUTUREX_NOTIFY_SUBSECTION_SUBJECT_MESSAGE.format(**email_context),
        "plaintext_msg": course_email_template.render_plaintext("", email_context),
        "html_msg": course_email_template.render_htmltext("", email_context),
    }
