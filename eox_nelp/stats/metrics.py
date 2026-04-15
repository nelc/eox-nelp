"""eox-nelp Metrics file.

functions:
    get_cached_courses: Return visible courses.
    get_course_metrics: Return the metric for the given course_key.
    get_learners_metric: Return number of learners, for the visible courses.
    get_instructors_metric: Return number of instructors, for the visible courses.
    get_courses_metrics: Return metrics for the visible courses.
    get_course_certificates_metric: Return a dict metric representin the certificates of a course.
"""
from crum import get_current_request
from django.conf import settings
from edx_django_utils.db.read_replica import use_read_replica_if_available
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from eox_core.edxapp_wrapper.users import get_user_signup_source

from eox_nelp.edxapp_wrapper.branding import get_visible_courses
from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.edxapp_wrapper.student import CourseAccessRole, CourseEnrollment
from eox_nelp.stats.decorators import cache_method

GeneratedCertificate = get_generated_certificate()
UserSignupSource = get_user_signup_source()


@cache_method
def get_cached_courses(tenant):  # pylint: disable=unused-argument
    """
    Returns the visible courses. This method is just a wrapper of get_visible_courses that
    allows to cache the result.

    Args:
        tenant<str>: String tenant identifier(site.domain)

    Return:
        list[<CourseOverview>]: List of CourseOverview records.
    """
    return get_visible_courses()


@cache_method
def get_course_metrics(course_key):
    """
    This allows to get the course stats metrics based on the course key.

    Args:
        course_key<opaque-key>: Course identifier.

    Return:
        <Dictionary>: Contains the course's metrics.
    """
    stats_settings = getattr(settings, "STATS_SETTINGS", {})
    course = modulestore().get_course(course_key)
    chapters = course.get_children()

    sequentials = []

    for chapter in chapters:
        sequentials += chapter.get_children()

    verticals = []

    for sequential in sequentials:
        verticals += sequential.get_children()

    allowed_block_types = stats_settings.get("API_XBLOCK_TYPES", [])
    components = {key: 0 for key in allowed_block_types}

    for vertical in verticals:
        for component in vertical.children:
            if component.block_type in allowed_block_types:
                components[component.block_type] = components.get(component.block_type, 0) + 1

    instructors = use_read_replica_if_available(
        CourseAccessRole.objects.filter(course_id=course_key).values('user').distinct(),
    ).count()
    learners = use_read_replica_if_available(
        CourseEnrollment.objects.filter(
            course=course_key,
            user__is_staff=False,
            user__is_superuser=False,
        ).values('user').distinct(),
    ).count()
    certificates = get_course_certificates_metric(course_key)

    return {
        "id": str(course_key),
        "name": course.display_name,
        "learners": learners,
        "instructors": instructors,
        "sections": len(chapters),
        "sub_sections": len(sequentials),
        "units": len(verticals),
        "components": components,
        "certificates": certificates,
    }


@cache_method
def get_learners_metric(tenant):
    """
    Returns the total of learners based on CourseEnrollments records.

    Args:
        tenant<str>: String tenant identifier(site.domain)

    Return:
        <int>: Total of learners.
    """
    request = get_current_request()
    tenant_courses = get_cached_courses(tenant)
    users_from_signup_source = use_read_replica_if_available(
        UserSignupSource.objects.filter(
            site=str(request.site),
            user__is_staff=False,
            user__is_superuser=False,
        ).values_list("user", flat=True).distinct(),
    )
    total_enrollments = use_read_replica_if_available(
        CourseEnrollment.objects.filter(
            course__in=tenant_courses,
            user__is_staff=False,
            user__is_superuser=False,
        ).exclude(
            user__in=users_from_signup_source,
        ).values('user').distinct(),
    ).count()

    return total_enrollments + users_from_signup_source.count()


@cache_method
def get_instructors_metric(tenant):  # pylint: disable=unused-argument
    """
    Returns the total of instructors based on the accessible orgs, and the CourseAccessRole records.

    Args:
        tenant<str>: This argument is used as identifier by the cache_method decorator.

    Return:
        <int>: Total of instructors.
    """
    current_site_orgs = configuration_helpers.get_current_site_orgs()

    return use_read_replica_if_available(
        CourseAccessRole.objects.filter(org__in=current_site_orgs).values('user').distinct(),
    ).count()


@cache_method
def get_courses_metrics(tenant):
    """
    Returns the total of courses and its metrics.

    Args:
        tenant<str>: String tenant identifier(site.domain)

    Return:
        <Dictionary>: Contains the courses' metrics.
    """
    courses = get_cached_courses(tenant)
    metrics = [get_course_metrics(course.id) for course in courses]

    return {"total_courses": courses.count(), "metrics": metrics}


def get_course_certificates_metric(course_key):
    """
    Returns the total of certificates in a course.

    Args:
        course_key<opaque-key>: Course identifier.

    Return:
        <Dictionary>: Contains certificates of course metric.
        {
                "verified": {...},
                "honor": {...},
                "audit": {},
                "professional": {...},
                "no-id-professional": {
                    "downloadable": 5,
                    "notpassing": 4,
                },
                "masters": {...},
                "executive-education": {...}
                "paid-executive-education":{...},
                "paid-bootcamp": {...},
                "total": 0
        }
    """
    certificates = {}
    course_certificates_qs = use_read_replica_if_available(
        GeneratedCertificate.objects.filter(course_id=course_key),
    )
    cert_statuses = [cert["status"] for cert in course_certificates_qs.values("status").distinct()]

    for mode in GeneratedCertificate.MODES:
        db_mode = mode[0]
        human_mode = mode[1]
        certificates[human_mode] = {
            cert_status: course_certificates_qs.filter(
                mode=db_mode,
                status=cert_status,
            ).values("user").distinct().count()
            for cert_status in cert_statuses
        }
    certificates["total"] = {
        cert_status: course_certificates_qs.filter(status=cert_status).values("user").distinct().count()
        for cert_status in cert_statuses
    }

    return certificates
