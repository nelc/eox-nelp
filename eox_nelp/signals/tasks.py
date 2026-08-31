"""Tasks that represent the logic of some work or undertaken that
signals receivers can use.

tasks:
    dispatch_futurex_progress: Logic to post progress data to futurex. It could be sync or async.
    update_mt_training_stage: Updates mt training stage.
    course_completion_mt_updater: Updates mt training stage based on completion logic.
"""
import logging
from datetime import timedelta

from celery import current_task, shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from eox_core.edxapp_wrapper.enrollments import get_enrollment
from eventtracking import tracker
from nelc_api_clients.clients.futurex import FuturexApiClient
from nelc_api_clients.clients.mt import MinisterOfTourismApiClient
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey

from eox_nelp.edxapp_wrapper.course_blocks import get_student_module_as_dict
from eox_nelp.edxapp_wrapper.course_modes import CourseMode
from eox_nelp.edxapp_wrapper.course_overviews import CourseOverview
from eox_nelp.edxapp_wrapper.grades import SubsectionGradeFactory
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.mt.models import MTTrainingStageDelivery
from eox_nelp.signals.exceptions import MTTrainingStageError
from eox_nelp.signals.utils import _user_has_passing_grade, get_completed_and_graded, get_completion_summary
from eox_nelp.utils import is_valid_national_id, normalize_national_id

logger = logging.getLogger(__name__)
User = get_user_model()
MT_SUCCESS_RESPONSE_CODE = 100
MT_UNACKNOWLEDGED_RETRY_WINDOW = timedelta(hours=6)
MT_RECONCILE_MAX_ATTEMPTS = 10
MT_RECONCILE_BATCH_SIZE = 200


@shared_task
def dispatch_futurex_progress(course_id, user_id, is_complete=None):
    """Dispatch the course progress of a user to Futurex platform.

    Args:
        course_id (str): Unique course identifier.
        user_id (str): User identifier.
        is_complete (bool): Determines is that hast complete the course
    """
    if not getattr(settings, "ACTIVATE_DISPATCH_FUTUREX_PROGRESS", False):
        return

    user = User.objects.get(id=user_id)
    user_has_passing_grade = is_complete if is_complete is not None else _user_has_passing_grade(user, course_id)

    progress_enrollment_data = _generate_progress_enrollment_data(
        user=user,
        course_id=course_id,
        user_has_passing_grade=user_has_passing_grade,
    )

    _post_futurex_progress(progress_enrollment_data)


def _post_futurex_progress(data):
    """Make post for enrollment http request to FuturexApiClient

    Args:
        data (dict): dict to send to futurex enrollment-progress path.
    """
    api_client = FuturexApiClient(
        client_id=settings.FUTUREX_CLIENT_ID,
        client_secret=settings.FUTUREX_CLIENT_SECRET,
        base_url=settings.FUTUREX_API_URL,
    )
    response = api_client.send_enrollment_progress(data)

    logger.info(
        "send_futurex_progress --- The data %s was sent to the futurex service host %s. The response was: %s",
        data,
        api_client.base_url,
        response,
    )


def _generate_progress_enrollment_data(user, course_id, user_has_passing_grade):
    """Generate the data that with the shape that use progress-enrollment endpoint of futurex.

    Args:
        user (User): User to map the enrollment data.
        course_id (str): Related course to map the enrollment data.
        user_has_passing_grade (bool): bool that check if the user grade pass the course pass grade.
                                                Defaults to False.

    Returns:
        progress_enrollment_data (dict): dict to send to futurex enrollment progress.
    """
    completion_summary = get_completion_summary(user, course_id)

    if completion_summary:
        complete_units = completion_summary["complete_count"]
        incomplete_units = completion_summary["incomplete_count"]
        locked_units = completion_summary["locked_count"]
        total_units = complete_units + incomplete_units + locked_units
        overall_progress = complete_units / total_units
    else:
        overall_progress = None

    enrollment, _ = get_enrollment(username=user.username, course_id=course_id)
    course_overview = CourseOverview.objects.get(id=course_id)

    social_user = user.social_auth.filter(
        provider="tpa-saml",
    ).exclude(Q(extra_data__isnull=True) | Q(extra_data=None)).first()

    if social_user:
        user_social_id = social_user.extra_data.get("uid")
    else:
        user_social_id = 16734
        logger.error(
            "User:%s doesn't have a social auth record, therefore is not possible to push progress.",
            user,
        )
        # return {}  uncomment after testing

    progress_enrollment_data = {
        "courseId": course_id,
        "userId": user_social_id,
        "approxTotalCourseHrs": getattr(course_overview, "effort", None),
        "overallProgress": overall_progress,
        "membershipState": enrollment.get("is_active", None),
        "enrolledAt": enrollment.get("created", None),
        "isCompleted": user_has_passing_grade,
    }

    logger.info(
        "send_futurex_progress --- Successful extraction of progress_enrollment_data: %s",
        progress_enrollment_data,
    )
    return progress_enrollment_data


@shared_task
def emit_subsection_attempt_event_task(usage_id, user_id):
    """This emits the event nelc.eox_nelp.grades.subsection.submitted when
    any component of a graded subsection has been attempted.

    Args:
        usage_id (str): component usage id.
        user_id (str): User identifier.
    """
    def get_attempts(subsection):
        """Inner method that returns the total of subsection attempts"""
        attempts = 0

        for unit in subsection.get_children():
            for component in unit.get_children():
                student_module = get_student_module_as_dict(
                    user,
                    usage_key.course_key,
                    component.location,
                )
                attempts += student_module.get("attempts", 0)

        return attempts

    store = modulestore()
    user = User.objects.get(id=user_id)
    usage_key = UsageKey.from_string(usage_id)
    vertical = store.get_item(store.get_parent_location(usage_key))
    subsection = vertical.get_parent()
    course = store.get_course(usage_key.course_key)
    subsection_grade_factory = SubsectionGradeFactory(user, course=course)
    subsection_grade = subsection_grade_factory.create(subsection=subsection, read_only=True, force_calculate=True)

    if subsection_grade.graded:
        tracker.emit(
            "nelc.eox_nelp.grades.subsection.submitted",
            {
                "user_id": user_id,
                "course_id": str(usage_key.context_key),
                "block_id": str(subsection_grade.location),
                "submitted_at": timezone.now().strftime("%Y-%m-%d, %H:%M:%S"),
                "earned": subsection_grade.graded_total.earned,
                "possible": subsection_grade.graded_total.possible,
                "percent": subsection_grade.percent_graded,
                "attempts": get_attempts(subsection),
            }
        )


def _get_mt_delivery(national_id, course_id, stage_result):
    """Return the delivery record for a result, creating it when it is new.

    Bookkeeping must never stop a delivery, so a database failure here is logged and
    None is returned, which makes the caller fall back to sending unconditionally.
    """
    try:
        delivery, _ = MTTrainingStageDelivery.objects.get_or_create(  # pylint: disable=no-member
            national_id=national_id,
            course_id=course_id,
            stage_result=stage_result,
        )

        if delivery.user_id is None:
            user = User.objects.filter(extrainfo__national_id=national_id).first()

            if user:
                delivery.user = user
                delivery.save(update_fields=["user"])

        return delivery
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not read the MT delivery record for course_id=%s, national_id=%s, stage_result=%s.",
            course_id,
            national_id,
            stage_result,
        )

        return None


def _mt_delivery_is_due(delivery):
    """Whether a result should be sent now.

    An acknowledged result is never sent again. An unacknowledged one is held for the
    retry window, which is what stops the completion receiver re-sending it on every
    BlockCompletion save. A missing record means bookkeeping failed, and a delivery is
    worth more than a duplicate, so it is sent.
    """
    if delivery is None:
        return True

    if delivery.acknowledged:
        return False

    if not delivery.attempts:
        return True

    return delivery.updated_at <= timezone.now() - MT_UNACKNOWLEDGED_RETRY_WINDOW


def _record_mt_delivery(delivery, response):
    """Store the outcome of a send against its delivery record.

    Failures here are logged and swallowed for the same reason as `_get_mt_delivery`:
    losing the bookkeeping is recoverable, losing the delivery is not.
    """
    if delivery is None:
        return

    try:
        acknowledged = response.get("responseCode") == MT_SUCCESS_RESPONSE_CODE
        delivery.attempts += 1
        delivery.last_response_code = str(response.get("responseCode"))[:16]
        delivery.last_response_message = str(
            response.get("responseMessage") or response.get("message") or ""
        )

        if acknowledged and not delivery.acknowledged:
            delivery.acknowledged = True
            delivery.acknowledged_at = timezone.now()

        delivery.save(update_fields=[
            "attempts",
            "last_response_code",
            "last_response_message",
            "acknowledged",
            "acknowledged_at",
            "updated_at",
        ])
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not record the MT delivery outcome for course_id=%s, national_id=%s, stage_result=%s.",
            delivery.course_id,
            delivery.national_id,
            delivery.stage_result,
        )


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def update_mt_training_stage(course_id, national_id, stage_result):
    """Sets MinisterOfTourismApiClient and updates the training stage base on the
    input arguments.

    The same update is sent multiple times, since the completion receiver runs on every
    BlockCompletion save, so an already sent result is skipped based on its delivery
    record. An acknowledged result is never sent again, an unacknowledged one is allowed
    again once the retry window has passed so it keeps being reattempted.

    Arguments:
        course_id (str): Unique course identifier.
        national_id (str): User identifier.
        stage_result (int): Representation of pass or fail result, 1 for pass  2 for fail.

    Raises:
        MTTrainingStageError: When the response code is not a success one, so the task is retried.
    """
    national_id = normalize_national_id(national_id)

    if not is_valid_national_id(national_id):
        logger.error(
            "Skipped update_training_stage with course_id=%s, stage_result=%s. Invalid national_id: %s",
            course_id,
            stage_result,
            national_id,
        )

        return

    delivery = _get_mt_delivery(national_id, course_id, stage_result)
    is_retry = bool(getattr(getattr(current_task, "request", None), "retries", 0))

    if not is_retry and not _mt_delivery_is_due(delivery):
        logger.debug(
            "Skipped update_training_stage with course_id=%s, national_id=%s, stage_result=%s. Already sent.",
            course_id,
            national_id,
            stage_result,
        )

        return

    api_client = MinisterOfTourismApiClient(
        user=settings.MINISTER_OF_TOURISM_USER,
        password=settings.MINISTER_OF_TOURISM_PASSWORD,
        base_url=settings.MINISTER_OF_TOURISM_API_URL,
    )

    response = api_client.update_training_stage(
        course_id=course_id,
        national_id=national_id,
        stage_result=stage_result,
    )

    _record_mt_delivery(delivery, response)

    if response.get("responseCode") == MT_SUCCESS_RESPONSE_CODE:
        logger.info(
            "Called update_training_stage with course_id=%s, national_id=%s, stage_result=%s. Response: %s",
            course_id,
            national_id,
            stage_result,
            response,
        )

        return

    logger.error(
        "Failed update_training_stage with course_id=%s, national_id=%s, stage_result=%s. Response: %s",
        course_id,
        national_id,
        stage_result,
        response,
    )

    raise MTTrainingStageError(
        f"The training stage was not acknowledged for course_id={course_id}, "
        f"national_id={national_id}, stage_result={stage_result}."
    )


@shared_task
def reconcile_mt_training_stages(limit=None):
    """Re-send every training stage result the partner has never acknowledged.

    Delivery is edge-triggered: COURSE_GRADE_NOW_PASSED fires once per learner per
    course and never fires again, so a result lost at that instant is lost for good
    and only surfaces when the partner asks about it. This closes that gap by
    walking the delivery records instead of waiting for another event.

    Results are handed to `update_mt_training_stage`, which applies the retry window
    itself, so a row picked up here before its window has passed is a no-op rather
    than a duplicate send.

    Arguments:
        limit (int): Maximum number of results to re-send in this run. Defaults to
            MT_RECONCILE_BATCH_SIZE, which bounds how much traffic one run can send
            to the partner.
    """
    due_before = timezone.now() - MT_UNACKNOWLEDGED_RETRY_WINDOW
    pending = MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
        acknowledged=False,
        attempts__lt=MT_RECONCILE_MAX_ATTEMPTS,
        updated_at__lte=due_before,
    ).order_by("updated_at")[:limit or MT_RECONCILE_BATCH_SIZE]

    unacknowledged_total = MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
        acknowledged=False,
    ).count()

    sent = 0

    for delivery in pending:
        update_mt_training_stage.delay(
            course_id=delivery.course_id,
            national_id=delivery.national_id,
            stage_result=delivery.stage_result,
        )
        sent += 1

    # Logged at ERROR so the backlog is alertable: a number that stops falling means
    # deliveries are being lost silently again.
    logger.error(
        "MT reconciliation re-sent %s results. %s results remain unacknowledged.",
        sent,
        unacknowledged_total,
    )

    return {"resent": sent, "unacknowledged": unacknowledged_total}


@shared_task
def course_completion_mt_updater(user_id, course_id, stage_result, force_graded=None):
    """This executes the update_mt_training_stage task synchronously based on the following conditions:

        1. incomplete_count is 0, that means that the user has completed the whole course.
        2. force_graded is False and the course is not graded or force_graded is True and the course is graded.

    Arguments:
        course_id (str): Unique course identifier.
        national_id (str): User identifier.
    """
    user = User.objects.get(id=user_id)
    extra_info = getattr(user, "extrainfo", None)
    national_id = extra_info.national_id if extra_info and extra_info.national_id else user.username
    is_complete, graded = get_completed_and_graded(user_id, course_id)

    if not is_complete or (force_graded and not graded) or (not force_graded and graded):
        return

    update_mt_training_stage(
        course_id=course_id,
        national_id=national_id,
        stage_result=stage_result,
    )


@shared_task
def set_default_advanced_modules(user_id, course_id):
    """
    Updates the `advanced_modules` field of a course with the default advanced modules defined by
    the course's organization.

    This process retrieves the advanced modules configured at the organization level of the course
    from the site configuration (using `configuration_helpers.get_value_for_org`). It then adds these
    modules to the course's `advanced_modules` list (ensuring no duplicates are present).

    The update is performed in the **modulestore**, which stores the course information in the Mongo database.

    Args:
        user_id (int): The ID of the user performing the update.
        course_id (str): The ID of the course to be updated, represented as a string.

    Returns:
        None: The function does not return any value but performs an update in the **modulestore**.
    """
    store = modulestore()
    course_key = CourseKey.from_string(course_id)
    course = store.get_course(course_key)
    default_modules = configuration_helpers.get_value_for_org(
        course_key.org,
        "DEFAULT_ADVANCED_MODULES",
        getattr(settings, "DEFAULT_ADVANCED_MODULES", []),
    )
    course.advanced_modules = list(set(course.advanced_modules + default_modules))
    store.update_item(course, user_id)


@shared_task
def create_course_mode(course_id, mode_slug):
    """
    Asynchronous task to create a specific CourseMode for a newly created course.

    This task parses the course key string, fetches the corresponding CourseOverview,
    and creates the requested CourseMode if it doesn't already exist.

    Args:
        course_id (str): The string representation of the course key
                              (e.g., 'course-v1:edX+DemoX+Demo_Course').
        mode_slug (str): The slug of the mode to be created (e.g., 'audit', 'honor').

    Returns:
        None
    """
    try:
        course_key = CourseKey.from_string(course_id)
        course_overview = CourseOverview.objects.get(id=course_key)

        _, created = CourseMode.objects.get_or_create(
            course=course_overview,
            mode_slug=mode_slug,
            defaults={
                'mode_display_name': course_id,
            }
        )

        if created:
            logger.info(
                "Successfully created '%s' course mode for course %s",
                mode_slug,
                course_id
            )
        else:
            logger.info(
                "Course mode '%s' already exists for course %s",
                mode_slug,
                course_id
            )

    except InvalidKeyError:
        logger.error(
            "Cannot create course mode. Invalid course key string provided: %s",
            course_id
        )
    except CourseOverview.DoesNotExist:
        logger.error(
            "Cannot create course mode. CourseOverview for key %s does not exist.",
            course_id
        )
