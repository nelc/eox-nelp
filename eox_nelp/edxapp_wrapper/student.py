"""Wrapper for modules in common student app.
This contains all the required dependencies from student common app.
Attributes:
    backend:Imported module by using the plugin settings.
    CourseEnrollment: Wrapper CourseEnrollment model.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_STUDENT_BACKEND)

CourseEnrollment = backend.get_course_enrollment_model()
CourseAccessRole = backend.get_course_access_role_model()
UserProfile = backend.get_user_profile_model()
roles = backend.get_student_roles()
anonymous_id_for_user = backend.get_anonymous_id_for_user()
CourseEnrollmentAdmin = backend.get_course_enrollment_admin()
AnonymousUserId = backend.get_anonymous_user_id_model()
auth = backend.get_student_auth()
