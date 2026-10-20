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
from django.db.models import F, Q
from django.utils import timezone
from eox_core.edxapp_wrapper.enrollments import get_enrollment
from eox_tenant.constants import LMS_CONFIG_COLUMN
from eox_tenant.signals import _update_settings
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
# The partner's response codes that mean it holds the result. This is the only place a
# code is mapped to an outcome: 110 currently means both "registration not found" and
# "already recorded", so it is left out and retried. When the partner splits it, the
# "already recorded" code goes here and "registration not found" stays out.
MT_ACKNOWLEDGED_RESPONSE_CODES = frozenset({100})
# How often an unacknowledged result is sent again, by its age since the first send:
# (age up to which the interval applies, interval). Past the last age it is abandoned.
MT_RETRY_SCHEDULE = (
    (timedelta(hours=12), timedelta(hours=1)),
    (timedelta(days=30), timedelta(days=1)),
)
MT_RETRY_TAIL = MT_RETRY_SCHEDULE[-1][0]
# Allowance for when a run starts, so a result sent at 10:00:30 is due again at the
# 11:00 run rather than skipping to 12:00.
MT_RETRY_SLACK = timedelta(minutes=5)
MT_RECONCILE_BATCH_SIZE = 200
MT_TENANT_DOMAIN = "mt.futurex.sa"


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


def _mt_delivery_due_filter(now):
    """Filter matching the delivery records that are due to be sent at `now`.

    A result never sent is always due. Otherwise it is due once the interval for its
    age in MT_RETRY_SCHEDULE has passed since it was last sent. Past the schedule the
    last interval still applies: the tail only bounds what the reconciliation picks
    up, so a result re-sent by hand or by a new event later still goes out, at most
    once per interval.
    """
    due = Q(attempts=0)

    for age_limit, interval in MT_RETRY_SCHEDULE[:-1]:
        due |= Q(created_at__gt=now - age_limit, updated_at__lte=now - interval + MT_RETRY_SLACK)

    return due | Q(updated_at__lte=now - MT_RETRY_SCHEDULE[-1][1] + MT_RETRY_SLACK)


def _claim_mt_delivery(delivery, is_retry):
    """Take the right to send a result, so only one of several parallel sends proceeds.

    The completion receiver and the pass event can queue the same result several
    times within milliseconds. Reading the record and then sending lets every copy
    see it as unsent, so the claim is a single conditional UPDATE instead: the
    database lets exactly one copy change the row, and the rest find nothing to
    change and skip. An acknowledged result can never be claimed.

    A Celery retry of the copy that already holds the claim skips the due check,
    since it is the same send. A missing record means bookkeeping failed, and a
    delivery is worth more than a duplicate, so it is sent.

    Returns:
        bool: Whether this call may send the result.
    """
    if delivery is None:
        return True

    now = timezone.now()
    claimable = MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
        pk=delivery.pk,
        acknowledged=False,
    )

    if not is_retry:
        claimable = claimable.filter(_mt_delivery_due_filter(now))

    try:
        return bool(claimable.update(attempts=F("attempts") + 1, updated_at=now))
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not claim the MT delivery record for course_id=%s, national_id=%s, stage_result=%s.",
            delivery.course_id,
            delivery.national_id,
            delivery.stage_result,
        )

        return True


def _record_mt_delivery(delivery, response):
    """Store the outcome of a send against its delivery record.

    Every write is a conditional UPDATE on unacknowledged rows, never a save of the
    instance loaded before the send: a parallel send may have been acknowledged in
    the meantime, and saving a stale instance would write its acknowledgement back
    to False. So `acknowledged` only ever goes from False to True, and an
    acknowledged row keeps the response that acknowledged it.

    Failures here are logged and swallowed for the same reason as `_get_mt_delivery`:
    losing the bookkeeping is recoverable, losing the delivery is not.
    """
    if delivery is None:
        return

    response_code = response.get("responseCode")
    outcome = {
        "last_response_code": None if response_code is None else str(response_code)[:16],
        "last_response_message": str(response.get("responseMessage") or response.get("message") or ""),
    }

    if response_code in MT_ACKNOWLEDGED_RESPONSE_CODES:
        outcome.update(acknowledged=True, acknowledged_at=timezone.now())

    try:
        MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
            pk=delivery.pk,
            acknowledged=False,
        ).update(**outcome)
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "Could not record the MT delivery outcome for course_id=%s, national_id=%s, stage_result=%s.",
            delivery.course_id,
            delivery.national_id,
            delivery.stage_result,
        )


def _mt_delivery_is_acknowledged(delivery):
    """Whether the result has been acknowledged, possibly by a parallel send."""
    if delivery is None:
        return False

    try:
        return MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
            pk=delivery.pk,
            acknowledged=True,
        ).exists()
    except Exception:  # pylint: disable=broad-except
        return False


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def update_mt_training_stage(course_id, national_id, stage_result):
    """Sets MinisterOfTourismApiClient and updates the training stage base on the
    input arguments.

    The same update is queued multiple times, since the completion receiver runs on every
    BlockCompletion save, so each send first claims its delivery record and only one
    copy proceeds. An acknowledged result is never sent again, an unacknowledged one is
    sent again on MT_RETRY_SCHEDULE until it is acknowledged or abandoned.

    Arguments:
        course_id (str): Unique course identifier.
        national_id (str): User identifier.
        stage_result (int): Representation of pass or fail result, 1 for pass  2 for fail.

    Raises:
        MTTrainingStageError: When the result is not acknowledged, so the task is retried.
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

    if not _claim_mt_delivery(delivery, is_retry):
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

    if response.get("responseCode") in MT_ACKNOWLEDGED_RESPONSE_CODES:
        logger.info(
            "Called update_training_stage with course_id=%s, national_id=%s, stage_result=%s. Response: %s",
            course_id,
            national_id,
            stage_result,
            response,
        )

        return

    if _mt_delivery_is_acknowledged(delivery):
        # A parallel send was acknowledged, so this rejection is the partner refusing a
        # duplicate. Retrying it would only send the duplicate again.
        logger.info(
            "Ignored update_training_stage response with course_id=%s, national_id=%s, stage_result=%s, "
            "already acknowledged. Response: %s",
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


def bind_mt_tenant():
    """Bind this process's settings to the MT tenant so queued tasks carry it.

    The MT credentials live only in the tenant's lms_configs. eox-tenant stamps every
    published task with `settings.EDNX_TENANT_DOMAIN`, overwriting any
    `eox_tenant_sender` kwarg, and the worker binds that tenant before the task runs.
    Outside a request (a CronJob or a shell) that setting is unset, so the worker
    falls back to global settings and the task dies on the missing credentials.

    Returns:
        bool: True when the settings now belong to the MT tenant.
    """
    domain = getattr(settings, "MT_TENANT_DOMAIN", MT_TENANT_DOMAIN)
    _update_settings(domain, LMS_CONFIG_COLUMN)

    return getattr(settings, "EDNX_TENANT_DOMAIN", None) == domain


@shared_task
def reconcile_mt_training_stages(limit=None):
    """Re-send every training stage result the partner has never acknowledged.

    Delivery is edge-triggered: COURSE_GRADE_NOW_PASSED fires once per learner per
    course and never fires again, so a result lost at that instant is lost for good
    and only surfaces when the partner asks about it. This closes that gap by
    walking the delivery records instead of waiting for another event.

    Results are picked by MT_RETRY_SCHEDULE: hourly while young, then daily, until
    they are older than MT_RETRY_TAIL and abandoned. They are handed to
    `update_mt_training_stage`, which claims each one again, so a result a parallel
    send has just taken is a no-op rather than a duplicate send.

    Arguments:
        limit (int): Maximum number of results to re-send in this run. Defaults to
            MT_RECONCILE_BATCH_SIZE, which bounds how much traffic one run can send
            to the partner.

    Returns:
        dict: `resent` this run, `actionable` results still to be retried, and
            `abandoned` results older than the retry tail.
    """
    now = timezone.now()
    unacknowledged = MTTrainingStageDelivery.objects.filter(  # pylint: disable=no-member
        acknowledged=False,
    )
    retryable = unacknowledged.filter(created_at__gt=now - MT_RETRY_TAIL)
    pending = retryable.filter(
        _mt_delivery_due_filter(now),
    ).order_by("updated_at")[:limit or MT_RECONCILE_BATCH_SIZE]

    # Split the backlog by whether anything will still be done about it. Rows past the
    # retry tail are never retried again, so counting them alongside the retryable
    # ones produces a number that can only rise, and an alert that can only become
    # noise.
    actionable = retryable.count()
    abandoned = unacknowledged.count() - actionable

    sent = 0

    if pending and not bind_mt_tenant():
        logger.error(
            "MT reconciliation could not bind the MT tenant, so nothing was re-sent. "
            "%s awaiting acknowledgement.",
            actionable,
        )

        return {"resent": sent, "actionable": actionable, "abandoned": abandoned}

    for delivery in pending:
        update_mt_training_stage.delay(
            course_id=delivery.course_id,
            national_id=delivery.national_id,
            stage_result=delivery.stage_result,
        )
        sent += 1

    # ERROR only when something is still owed, so the level carries information: a run
    # with nothing outstanding is not a problem and must not page anyone.
    log = logger.error if actionable else logger.info
    log(
        "MT reconciliation re-sent %s results. %s awaiting acknowledgement, "
        "%s abandoned after %s days.",
        sent,
        actionable,
        abandoned,
        MT_RETRY_TAIL.days,
    )

    return {"resent": sent, "actionable": actionable, "abandoned": abandoned}


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
