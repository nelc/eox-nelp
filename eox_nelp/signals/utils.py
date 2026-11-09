"""Common function for the signals module.

Functions:
    _generate_external_certificate_data: Generates dict data from CertificateData.
    _user_has_passing_grade: Determines if the user has a passing grade
    complete_lti_block_from_ags_score: Marks an LTI block complete when the tool reports the activity Completed.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from eox_core.edxapp_wrapper.courseware import get_courseware_courses
from eox_core.edxapp_wrapper.grades import get_course_grade_factory
from opaque_keys.edx.keys import CourseKey, UsageKey

from eox_nelp.edxapp_wrapper.completion import BlockCompletion
from eox_nelp.edxapp_wrapper.lti_consumer import get_user_from_external_user_id
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.utils import is_valid_national_id

CourseGradeFactory = get_course_grade_factory()
User = get_user_model()
courses = get_courseware_courses()
LTI_ACTIVITY_COMPLETED = "Completed"


def _generate_external_certificate_data(time, certificate_data):
    """This generates a dictionary from a CertificateData class

    Args:
        time<Datetime>: Date when the certificate was created.
        certificate<CertificateData>: This an instance of the class defined in this link
            https://github.com/eduNEXT/openedx-events/blob/main/openedx_events/learning/data.py#L100
            and will provide of the user certificate data.

    Raises:
        KeyError: if the current course has not been set with its group code the method will raise
            this exception.

    Returns:
        Dict: certificate data
    """
    user = User.objects.get(id=certificate_data.user.id)
    group_codes = getattr(settings, "EXTERNAL_CERTIFICATES_GROUP_CODES", {})
    course_id = str(certificate_data.course.course_key)
    extra_info = getattr(user, "extrainfo", None)

    if extra_info:
        national_id = extra_info.national_id
        arabic_name = extra_info.arabic_name
    else:
        national_id = user.username
        arabic_name = ""

    national_id = national_id[:10]  # saml association extra filter

    return {
        "reference_id": generate_reference_id(national_id, course_id),
        "created_at": str(time.date()),
        "expiration": None,
        "grade": float(certificate_data.grade) * 100,
        "is_passing": _user_has_passing_grade(user, course_id),
        "group_code": group_codes[course_id],
        "user": {
            "national_id": national_id,
            "english_name": certificate_data.user.pii.name,
            "arabic_name": arabic_name,
        }
    }


def _user_has_passing_grade(user, course_id):
    """Determines if a user has passed a course based on the grading policies.

    Args:
        user<User>: Instace of Django User model.
        course_id<str>: Unique course identifier.
    Returns:
        course_grade.passed<bool>: True if the user has passed the course, otherwise False
    """
    course_grade = CourseGradeFactory().read(user, course_key=CourseKey.from_string(course_id))

    return course_grade.passed


def generate_reference_id(national_id, course_id):
    """Generate string of reference_id shape.
    Args:
        national_id<string>: Username of the user(national_id).
        course_id<str>: Unique course identifier.

    Returns:
        reference_id<str>: The string of reference_id representation.

    Raise:
        ValueError: National Id is not valid.
    """
    is_valid_national_id(national_id, raise_exception=True)

    return f"{national_id}~{course_id}"


def get_completion_summary(user, course_id):
    """Get completion summary of a user in a course.

    Args:
        user (User): User object
        course_id (CourseLocator): Unique course identifier.

    Returns:
        completion_summary(dict): Completion summary of the user in the course.
    """
    course_key = CourseKey.from_string(course_id)

    return courses.get_course_blocks_completion_summary(course_key, user)


def get_completed_and_graded(user_id, course_id):
    """Get the is_complete or is graded info related user and course.
    Returns a tuple with that info.

    Args:
        user_id (str): User id to analize completion and grading.
        course_id (str): CourseId to analize completion and grading.

    Returns:
        is_complete(bool), is_graded(bool): bool flags telling that the course is complete or graded.
    """
    user = User.objects.get(id=user_id)
    course_key = CourseKey.from_string(course_id)
    descriptor = modulestore().get_course(course_key)
    grading_policy = descriptor.grading_policy
    completion_summary = get_completion_summary(user, course_id)
    is_complete = completion_summary["incomplete_count"] == 0
    is_graded = bool(grading_policy["GRADER"])

    return is_complete, is_graded


def _lti_ags_score_skip_reason(score):
    """Why an AGS score must not complete its block, from the score alone, or None when it may.

    Args:
        score<LtiAgsScore>: The AGS score row.

    Returns:
        str or None: not_completed, scored or out_of_scope.
    """
    if score.activity_progress != LTI_ACTIVITY_COMPLETED:
        return "not_completed"

    if score.score_given is not None:
        return "scored"

    line_item = score.line_item
    resource_link_id = str(line_item.resource_link_id or "")

    # Same guard as lti_consumer: a tool may only write to the block of its own configuration.
    if not resource_link_id or resource_link_id != str(line_item.lti_configuration.location):
        return "out_of_scope"

    return None


def complete_lti_block_from_ags_score(score, apply=True, only_user_id=None):
    """Mark the LTI block of an AGS score complete when the tool reports the activity Completed.

    Some tools (AWS Skill Builder) only send `activityProgress=Completed` and never a score, while
    lti_consumer only acts on FullyGraded scores, so the learner's progress was dropped. Scored
    rows are left to lti_consumer's own grade path, so the two never write the same block.

    Args:
        score<LtiAgsScore>: The AGS score row.
        apply (bool): Write the completion. False only reports what would happen.
        only_user_id (int): When set, rows of any other user are skipped.

    Returns:
        str: Outcome label: not_completed, scored, out_of_scope, unknown_user, other_user,
            already_complete or completed.
    """
    skip_reason = _lti_ags_score_skip_reason(score)

    if skip_reason:
        return skip_reason

    user = get_user_from_external_user_id(score.user_id)

    if user is None:
        return "unknown_user"

    if only_user_id is not None and user.id != only_user_id:
        return "other_user"

    block_key = UsageKey.from_string(str(score.line_item.resource_link_id))

    if BlockCompletion.objects.filter(
        user=user, context_key=block_key.context_key, block_key=block_key, completion__gte=1,
    ).exists():
        return "already_complete"

    if apply:
        BlockCompletion.objects.submit_completion(user=user, block_key=block_key, completion=1.0)

    return "completed"
