"""Permissions for Programs API v1."""
from opaque_keys.edx.keys import CourseKey
from rest_framework.permissions import BasePermission

from eox_nelp.edxapp_wrapper.student import auth, roles


class HasStudioWriteAccess(BasePermission):
    """
    Check if the user has write access to studio.
    """

    def has_permission(self, request, view):
        """
        Check if the user has write access to studio.
        """
        course_id = view.kwargs.get("course_id")
        course_key = CourseKey.from_string(course_id)
        return auth.has_studio_write_access(request.user, course_key)


class ProgramsLookupPermission(BasePermission):
    """
    Permission class to check if the user has access to view program lookup.
    """

    def has_permission(self, request, view):
        """
        Check if the user has access to view program lookup.
        """
        org = request.data.get("org", None)
        return bool(
            roles.GlobalStaff().has_user(request.user) or roles.OrgInstructorRole(org=org).has_user(request.user)
        )
