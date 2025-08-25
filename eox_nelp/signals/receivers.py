"""Functions that extend the edx-platform behavior based on Django
signals, to check which method is used, go to the apps.py file and
verify the connections.

Functions:
    block_completion_progress_publisher: it will publish the user progress based on post_save signal.
    course_grade_changed_progress_publisher: it will publish the user progress based on COURSE_GRADE_CHANGED signal.
    create_course_notifications: this will create upcoming notifications based on the sub-section due dates.
    certificate_publisher: Publish the user certificate data to the NELC certificates service.
    include_tracker_context: Append tracker context to async task data.
    update_async_tracker_context: Update tracker context based on the task data.
    emit_subsection_attempt_event: Emits an event when a graded subsection has been attempted.
    mt_course_completion_handler: Updates mt training stage based on completion events.
    mt_course_passed_handler: Updates mt training stage based on COURSE_GRADE_NOW_PASSED signal.
    mt_course_failed_handler: Updates mt training stage based on COURSE_GRADE_NOW_FAILED signal.
"""
import logging

from crum import get_current_user
from django.conf import settings
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from eox_core.edxapp_wrapper.grades import get_course_grade_factory
from eox_core.edxapp_wrapper.users import get_user_signup_source
from eox_tenant.tenant_wise.proxies import TenantSiteConfigProxy
from eventtracking import tracker
from openedx_events.learning.data import CertificateData, CourseData, UserData, UserPersonalData

from eox_nelp.edxapp_wrapper.contentstore import CourseAboutSearchIndexer
from eox_nelp.edxapp_wrapper.modulestore import SignalHandler
from eox_nelp.external_certificates.tasks import create_external_certificate
from eox_nelp.notifications.tasks import create_course_notifications as create_course_notifications_task
from eox_nelp.payment_notifications.models import PaymentNotification
from eox_nelp.pearson_vue_engine.tasks import real_time_import_task_v2
from eox_nelp.signals.tasks import (
    course_completion_mt_updater,
    dispatch_futurex_progress,
    emit_subsection_attempt_event_task,
    set_default_advanced_modules,
    update_mt_training_stage,
)
from eox_nelp.signals.utils import _generate_external_certificate_data, get_completed_and_graded

User = get_user_model()
UserSignupSource = get_user_signup_source()
LOGGER = logging.getLogger(__name__)
CourseGradeFactory = get_course_grade_factory()


def block_completion_progress_publisher(instance, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the post_save BlockCompletion signal
    and this will publish the user progress to Futurex platform.

    Args:
        instance<Blockcompletion>: Instance of BlockCompletion model.
    """
    dispatch_futurex_progress.delay(
        course_id=str(instance.context_key),
        user_id=instance.user_id,
    )


def emit_initialized_course_event(instance, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the post_save BlockCompletion signal
    and this checks how many BlockCompletion records exists, if there is only one record
    the `nelc.eox_nelp.initialized.course` event will be emitted.

    Args:
        instance<Blockcompletion>: Instance of BlockCompletion model.
    """
    completion_blocks = instance.user_learning_context_completion_queryset(instance.user, instance.context_key)

    if len(completion_blocks) == 1:
        tracker.emit(
            "nelc.eox_nelp.initialized.course",
            {
                "user_id": instance.user_id,
                "course_id": str(instance.context_key),
                "block_id": str(instance.block_key),
                "modified": instance.modified,
                "created": instance.created,
            }
        )


def course_grade_changed_progress_publisher(
    user,
    course_key,
    course_grade,
    **kwargs
):  # pylint: disable=unused-argument
    """This receiver is connected to the COURSE_GRADE_CHANGED signal
    and will publish user course progress based on the given data.

    Args:
        user<User>: Instance of Django User model.
        course_key<CourseLocator>: Opaque keys locator used to identify a course.
        course_grade<CourseGrade>: Grading class for a specific course.
    """
    dispatch_futurex_progress(
        course_id=str(course_key),
        user_id=user.id,
        is_complete=course_grade.passed,
    )


def create_course_notifications(course_key, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the course_published signal, that belong to
    the class SignalHandler from xmodule, and this will create upcoming notifications
    based on the sub-section due dates.

    Args:
        course_key<CourseLocator>: Opaque keys locator used to identify a course.
    """
    create_course_notifications_task.delay(course_id=str(course_key))


def certificate_publisher(certificate, metadata, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver that is connected to the CERTIFICATE_CREATED signal from 'openedx_events.learning.signals'.

    Basically this verifies that the publish action is active and validates the certificate mode in order
    to publish just certificates with valid modes. That behavior is controlled by the following settings:

    - ENABLE_CERTIFICATE_PUBLISHER<boolean>: If this is true the receiver will publish the certificate data,
    default is False.
    - CERTIFICATE_PUBLISHER_VALID_MODES<list[string]>: List of valid modes, default ['no-id-professional']

    Args:
        certificate<CertificateData>: This an instance of the class defined in this link
            https://github.com/eduNEXT/openedx-events/blob/main/openedx_events/learning/data.py#L100
            and will provide of the user certificate data.
        metadata <EventsMetadata>: Instance of the class defined in this link
            https://github.com/eduNEXT/openedx-events/blob/main/openedx_events/data.py#L29
    """
    if not getattr(settings, "ENABLE_CERTIFICATE_PUBLISHER", False):
        return

    default_modes = [
        "no-id-professional",
    ]
    valid_modes = getattr(settings, "CERTIFICATE_PUBLISHER_VALID_MODES", default_modes)

    if certificate.mode in valid_modes:
        LOGGER.info(
            "The %s certificate associated with the user <%s> and course <%s> has been already generated "
            "and its data will be sent to the NELC certificate service.",
            certificate.mode,
            certificate.user.pii.username,
            certificate.course.course_key,
        )
        create_external_certificate(
            external_certificate_data=_generate_external_certificate_data(
                time=metadata.time,
                certificate_data=certificate,
            ),
            user_id=certificate.user.id,
            course_id=certificate.course.course_key,
        )
    else:
        LOGGER.info(
            "The %s certificate associated with the user <%s> and course <%s> "
            "doesn't have a valid mode and therefore its data won't be published.",
            certificate.mode,
            certificate.user.pii.username,
            certificate.course.course_key,
        )


def enrollment_publisher(instance, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver that is connected to the course enrollment post_save signal and this will generate certificate
    data to publish it to the external service. That behavior is controlled by the following settings:

    - ENABLE_CERTIFICATE_PUBLISHER<boolean>: If this is true the receiver will publish the certificate data,
    default is False.
    - CERTIFICATE_PUBLISHER_VALID_MODES<list[string]>: List of valid modes, default ['no-id-professional']

    Note: This keeps the same certificate receiver settings since this will create an external certificate at
    the beginning of the course, then the certificate receiver will update the grade.

    Args:
        instance<CourseEnrollment>: This an instance of the model CourseEnrollment.
    """
    if not getattr(settings, "ENABLE_CERTIFICATE_PUBLISHER", False):
        return

    default_modes = [
        "no-id-professional",
    ]
    valid_modes = getattr(settings, "CERTIFICATE_PUBLISHER_VALID_MODES", default_modes)

    if instance.mode in valid_modes:
        LOGGER.info(
            "The %s enrollment associated with the user <%s> and course <%s> has been already generated "
            "and its data will be sent to the NELC certificate service.",
            instance.mode,
            instance.user.username,
            instance.course_id,
        )
        time = instance.created
        user = instance.user
        course_grade = CourseGradeFactory().read(user, course_key=instance.course_id)
        certificate = CertificateData(
            user=UserData(
                pii=UserPersonalData(
                    username=user.username,
                    email=user.email,
                    name=user.profile.name,
                ),
                id=user.id,
                is_active=user.is_active,
            ),
            course=CourseData(
                course_key=instance.course_id,
            ),
            mode=instance.mode,
            grade=course_grade.percent,
            current_status='downloadable' if course_grade.passed else 'not-passing',
            download_url='',
            name='',
        )

        create_external_certificate(
            external_certificate_data=_generate_external_certificate_data(
                time=time,
                certificate_data=certificate,
            ),
            user_id=user.id,
            course_id=instance.course_id,
        )
    else:
        LOGGER.info(
            "The %s enrollment associated with the user <%s> and course <%s> "
            "doesn't have a valid mode and therefore its data won't be published.",
            instance.mode,
            instance.user.username,
            instance.course_id,
        )


def create_usersignupsource_by_enrollment(instance, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver that is connected to the course enrollment post_save signal. This will generate a
    UserSignupSource record if possilbe
    based on the `SITE_NAME` tenant settings.
    If there is not SITE_NAME configurated this would be skipped with a log.

    Args:
        instance<CourseEnrollment>: This an instance of the model CourseEnrollment.
    """
    site_name = TenantSiteConfigProxy.get_value_for_org(instance.course_id.org, "SITE_NAME")

    if not site_name:
        LOGGER.info(
            "TenantSiteConfig related the course org %s has not `SITE_NAME` configurated to create usersignupsource "
            "for the user %s",
            instance.course_id.org,
            instance.user.username,
        )
        return

    usersignupsource, was_created = UserSignupSource.objects.get_or_create(user=instance.user, site=site_name)

    LOGGER.info(
        "UserSignupSource by enrollment managed and created=%s for user %s with site_name %s, and org %s",
        was_created,
        instance.user.username,
        usersignupsource.site,
        instance.course_id.org,
    )


def update_payment_notifications(instance, **kwargs):  # pylint: disable=unused-argument
    """This update the internal status of a payment notification record,
    if the enrollment is active an have the no-id-professional mode this will set
    the internal status as resolution_by_case_1
    """
    if not instance.is_active or instance.mode != "no-id-professional":
        return

    user = instance.user
    course_key = instance.course_id

    payment_notifications = PaymentNotification.objects.filter(  # pylint: disable=no-member
        cdtrans_lms_user_id=user.id,
        cdtrans_course_id=str(course_key),
        internal_status="case_1",
    )

    for payment_notification in payment_notifications:
        payment_notification.internal_status = "resolution_by_case_1"
        payment_notification.save()

        LOGGER.info(
            "The internal status of the payment notification with id %s has been updated to %s",
            payment_notification.id,
            payment_notification.internal_status,
        )


def include_tracker_context(body, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver used to add tracker context to the async process  to the task that need to be done.

    Dispatched before a celery task is published. Note that this is executed in the process sending the task.
    See:
        https://celery.readthedocs.io/en/latest/userguide/signals.html#before-task-publish
    """
    current_tracker = tracker.get_tracker()
    context = current_tracker.resolve_context()
    body["kwargs"]["tracker_context"] = context


def update_async_tracker_context(sender, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver that runs on the async process to update the tracker context.
    Dispatched before a task is executed.
    See:
       https://celery.readthedocs.io/en/latest/userguide/signals.html#task-prerun
    """
    request = sender.request
    tracker_context = request.get("kwargs", {}).pop("tracker_context", {})
    current_tracker = tracker.get_tracker()
    current_tracker.enter_context("asynchronous_context", tracker_context)


def emit_subsection_attempt_event(usage_id, user_id, *args, **kwargs):  # pylint: disable=unused-argument
    """This emits  the 'nelc.eox_nelp.grades.subsection.submitted' event
    when a graded subsection has been attempted.
    """
    emit_subsection_attempt_event_task.delay(
        usage_id=usage_id,
        user_id=user_id
    )


def mt_course_completion_handler(instance, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the post_save BlockCompletion signal and this executes
    the course_completion_mt_updater task, that basically updates the training stage based
    on the completion logic.

    Arguments:
        instance<Blockcompletion>: Instance of BlockCompletion model.
    """
    if not getattr(settings, "ACTIVATE_MT_COMPLETION_UPDATER", False):
        return

    course_completion_mt_updater.delay(
        user_id=instance.user_id,
        course_id=str(instance.context_key),
        stage_result=1,
    )


def mt_course_passed_handler(user, course_id, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the COURSE_GRADE_NOW_PASSED signal and this executes
    the update_mt_training_stage task, that updates the training stage with a result of 1 (PASS)

    Arguments:
        user <User>: Instance of auth user model.
        course_id <CourseLocator>: Course locator.
    """
    if not getattr(settings, "ACTIVATE_MT_TRAINING_STAGE", False):
        return

    extra_info = getattr(user, "extrainfo", None)
    national_id = extra_info.national_id if extra_info and extra_info.national_id else user.username

    update_mt_training_stage.delay(
        course_id=str(course_id),
        national_id=national_id,
        stage_result=1,
    )


def mt_course_failed_handler(user, course_id, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the COURSE_GRADE_NOW_FAILED signal and this executes
    the update_mt_training_stage task, that updates the training stage with a result of 2 (FAIL)

    Arguments:
        user <User>: Instance of auth user model.
        course_id <CourseLocator>: Course locator.
    """
    if not getattr(settings, "ACTIVATE_MT_COMPLETION_UPDATER", False):
        return

    course_completion_mt_updater.delay(
        user_id=user.id,
        course_id=str(course_id),
        stage_result=2,
        force_graded=True,
    )


def pearson_vue_course_completion_handler(instance, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the post_save BlockCompletion signal and this executes
    the pearson vue real_time_import_task , that basically runs the RTI pipeline
    on the completion logic.
    This sends only the user_id and course_id kwargs.

    Arguments:
        instance<Blockcompletion>: Instance of BlockCompletion model.
    """
    if not getattr(settings, "PEARSON_RTI_ACTIVATE_COMPLETION_GATE", False) or not str(instance.context_key) in getattr(
        settings, "PEARSON_ENGINE_COURSES_ENABLED", []
    ):
        return

    is_complete, graded = get_completed_and_graded(user_id=instance.user_id, course_id=str(instance.context_key))

    if graded or not is_complete:
        return

    LOGGER.info(
        "Initializing rti task for the user %s, action triggered by course completion status",
        instance.user_id,
    )

    real_time_import_task_v2.delay(
        user_id=instance.user_id,
        exam_id=str(instance.context_key),
        action_name="rti",
    )


def pearson_vue_course_passed_handler(user, course_id, **kwargs):  # pylint: disable=unused-argument
    """This receiver is connected to the COURSE_GRADE_NOW_PASSED
    https://github.com/openedx/edx-platform/blob/open-release/palm.master/openedx/core/djangoapps/signals/signals.py#L23
    signal and this execute the pearson vue real_time_import_task , that basically runs the RTI pipeline.(PASS)
    This sends the user_id, course_id, is_passing, and is_graded kwargs.

    Arguments:
        user <User>: Instance of auth user model.
        course_id <CourseLocator>: Course locator.
    """
    if not getattr(settings, "PEARSON_RTI_ACTIVATE_GRADED_GATE", False) or not str(course_id) in getattr(
        settings, "PEARSON_ENGINE_COURSES_ENABLED", []
    ):
        return

    LOGGER.info(
        "Initializing rti task for the user %s, action triggered by COURSE_GRADE_NOW_PASSED signal",
        user.id,
    )

    real_time_import_task_v2.delay(
        user_id=user.id,
        exam_id=str(course_id),
        action_name="rti",
    )


def receive_course_created(course, **kwargs):  # pylint: disable=unused-argument
    """
    Django signal receiver that triggers the `set_default_advanced_modules` async task when the
    `COURSE_CREATED` signal is sent.

    This function listens for the `COURSE_CREATED` signal and, upon receiving the signal, calls
    the asynchronous task `set_default_advanced_modules` to update the `advanced_modules` of the
    course. The task is executed with the `course_key` and the current user's ID.

    Args:
        course <CourseData>: CourseData instance
            https://github.com/openedx/openedx-events/blob/v9.10.0/openedx_events/content_authoring/data.py#L19
        **kwargs: Additional keyword arguments passed with the signal, if any.

    Returns:
        None: This function does not return any value. It triggers an asynchronous task.
    """
    user = get_current_user()

    if not user:
        LOGGER.warning("receive_course_created couldn't init set_default_advanced_modules since there is no user")
        return

    set_default_advanced_modules.apply_async(
        args=[user.id, str(course.course_key)],
        countdown=5,
    )


# The signal is defined inside a class, so the receiver must be connected this way instead of plugins standard.
@receiver(SignalHandler.course_deleted)
def listen_for_course_delete(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """
    This function is a verbatim copy of the implementation defined in:
    https://github.com/nelc/edx-platform/blob/open-release/redwood.nelp/cms/djangoapps/contentstore/signals/handlers.py#L167

    In the Teak release, importing the `handlers` module directly
    (e.g., `from cms.djangoapps.contentstore.signals import handlers`)
    introduces conflicts because that module transitively imports CMS-only
    models that are not valid in the LMS context.

    To avoid these conflicts, the handler implementation has been duplicated
    here. The only dependency required by this function is
    `CourseAboutSearchIndexer`, which can be safely imported without causing
    LMS issues.

    While this results in a small amount of duplicated code, it ensures that
    the course deletion signal is properly handled without introducing
    cross-app dependencies that would break the LMS environment.
    """
    CourseAboutSearchIndexer.remove_deleted_items(course_key)
