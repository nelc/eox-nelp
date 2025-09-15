"""Permissions for Programs API v1."""
from opaque_keys.edx.keys import CourseKey
from rest_framework.permissions import BasePermission

from eox_nelp.edxapp_wrapper.student import auth


class HasStudioWriteAccess(BasePermission):
    """
    Check if the user has write access to studio.
    """

    def has_permission(self, request, view):
        """
        Check if the user has write access to studio.
        """
        course_key_string = view.kwargs.get("course_key_string")
        course_key = CourseKey.from_string(course_key_string)
        return auth.has_studio_write_access(request.user, course_key)
