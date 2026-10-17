"""Wrapper with the edx-platform / edx-ace pieces the learner e-mails need.

Attributes:
    backend: Imported module by using the plugin settings.
    BaseMessageType: Platform base class of the ace messages (adds the tenant from-address).
    send_and_confirm: Send an ace message and say whether the delivery really happened.
    make_recipient: Ace recipient of a user.
    emulate_tenant_request: Context manager: a fake request on the tenant Site and with the tenant theme.
    get_site_for_domain: Site row of a tenant domain.
    get_base_context: Template context every ace frame expects (logo, platform name, ...).
    get_user_language: Language the learner saved in the account settings, or None.
    get_downloadable_certificate: The learner's downloadable certificate of a course, or None.
    get_certificate_url: Path of the certificate page.
    iter_downloadable_certificates: (user_id, course_id) of every downloadable certificate of an org.
    list_orgs: Orgs that have courses.
    find_started_courses / find_courses_ending / find_running_courses: Course rows (course_id, org, start, end).
    iter_enrollments: (user_id, created) of the active enrollments of a course.
    iter_progress: (user_id, percent 0..1) of the course-completion aggregates of a course at/over a minimum.
    get_progress: One learner's course completion, 0..1 (0 when there is no aggregate).
    is_enrolled / has_certificate: Active enrollment / downloadable certificate checks of one learner.
    get_course_path: Path of the course home page.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_LEARNER_EMAILS_BACKEND)

BaseMessageType = backend.BaseMessageType
send_and_confirm = backend.send_and_confirm
make_recipient = backend.make_recipient
emulate_tenant_request = backend.emulate_tenant_request
get_site_for_domain = backend.get_site_for_domain
get_base_context = backend.get_base_context
get_user_language = backend.get_user_language
get_downloadable_certificate = backend.get_downloadable_certificate
get_certificate_url = backend.get_certificate_url
iter_downloadable_certificates = backend.iter_downloadable_certificates
list_orgs = backend.list_orgs
find_started_courses = backend.find_started_courses
find_courses_ending = backend.find_courses_ending
find_running_courses = backend.find_running_courses
iter_enrollments = backend.iter_enrollments
iter_progress = backend.iter_progress
get_progress = backend.get_progress
is_enrolled = backend.is_enrolled
has_certificate = backend.has_certificate
get_course_path = backend.get_course_path
