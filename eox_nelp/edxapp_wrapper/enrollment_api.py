"""Wrapper with the edx-platform pieces the enrollment API override needs.

Attributes:
    backend: Imported module by using the plugin settings.
    enroll_email: Reserve (or directly enrol) a student by email.
    send_mail_to_student: Render and send one of the ace enrollment messages.
    get_email_params: Build the template context of those messages.
    emulate_http_request: Context manager that gives Celery code a request bound to a Site.
    get_course_overview: Course overview by course key, NotFound when missing.
    is_actively_enrolled: Whether the user has an active enrollment in the course.
    account_exists: Whether any account owns the email.
    user_on_site: Whether the user was created on / signed up through the given site domain.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_ENROLLMENT_API_BACKEND)

enroll_email = backend.enroll_email
send_mail_to_student = backend.send_mail_to_student
get_email_params = backend.get_email_params
emulate_http_request = backend.emulate_http_request
get_course_overview = backend.get_course_overview
is_actively_enrolled = backend.is_actively_enrolled
user_on_site = backend.user_on_site
account_exists = backend.account_exists
