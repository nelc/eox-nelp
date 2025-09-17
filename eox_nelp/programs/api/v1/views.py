"""Programs API v1 Views."""

from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from eox_core.edxapp_wrapper.courseware import get_courseware_courses
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.course_api.v1.views import NelpCourseListView
from eox_nelp.edxapp_wrapper.student import CourseEnrollment
from eox_nelp.programs.api.v1.permissions import HasStudioWriteAccess, ProgramsLookupPermission
from eox_nelp.programs.api.v1.serializers import ProgramLookupSerializer, ProgramsMetadataSerializer
from eox_nelp.programs.api.v1.utils import (
    get_program_lookup_representation,
    get_program_metadata,
    update_program_metadata,
)
from eox_nelp.utils import is_valid_national_id

User = get_user_model()
courses = get_courseware_courses()


def require_feature_enabled(feature_name):
    """Decorator to check if a feature is enabled before executing the method."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not settings.FEATURES.get(feature_name):
                return Response(
                    {"error": f"System Settings doesn't have enabled FEATURE {feature_name}"},
                    status=status.HTTP_501_NOT_IMPLEMENTED,
                )
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def require_national_id_query_param():
    """Decorator to check if national_id query parameter is valid if provided.
    If not provided, the view will proceed without filtering by national_id.
    Using the request user if not provided.
    Returns 400 if missing and 422 if invalid.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if self.request.query_params:
                if not (national_id := self.request.query_params.get("national_id", "")):
                    return Response(
                        {
                            "error": "MISSING_NATIONAL_ID",
                            "message": "national_id query parameter is required."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not is_valid_national_id(national_id):
                    return Response(
                        {
                            "error": "INVALID_NATIONAL_ID",
                            "message": "national_id must be digits only and 10–15 characters."
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


class ProgramsMetadataView(APIView):
    """
    API view for retrieving and updating program metadata by course ID.

    **Use Cases**
        - Retrieve metadata for a specific course program
        - Create or update program metadata for a course

    **Example Requests**
        GET /eox-nelp/api/programs/v1/metadata/course-v1:edx+cd101+23213
        POST /eox-nelp/api/programs/v1/metadata/course-v1:edx+cd101+23213

    **Authentication**
        Requires JWT token or session authentication

    **Response Values**
        Returns program metadata including:
        - trainer_type: Trainer type (integer, default 10)
        - Type_of_Activity: Activity type code (integer)
        - Mandatory: Mandatory flag ("01" or "00")
        - Program_ABROVE: Program approval flag ("01" or "00")
        - Program_code: Program code (string, max 64 characters)

    **Returns**
        * 200 on success with program metadata
        * 201 on successful creation/update
        * 400 on invalid data
        * 401 if authentication failed
        * 404 if course not found
    """

    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated, HasStudioWriteAccess]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer] if getattr(settings, "DEBUG", None) else [JSONRenderer]

    @require_feature_enabled("ENABLE_OTHER_COURSE_SETTINGS")
    def get(self, request, course_id):  # pylint: disable=unused-argument
        """
        Retrieve program metadata for the specified course ID.

        Args:
            request: HTTP request object
            course_id: Course identifier

        Returns:
            Response with program metadata or error
        """
        if not (program_metadata := get_program_metadata(course_id)):
            return Response({"error": "Program metadata not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProgramsMetadataSerializer(data=program_metadata)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_feature_enabled("ENABLE_OTHER_COURSE_SETTINGS")
    def post(self, request, course_id):
        """
        Create or update program metadata for the specified course ID.

        Args:
            request: HTTP request object containing program metadata
            course_id: Course identifier

        Returns:
            Response with updated program metadata or error
        """
        serializer = ProgramsMetadataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_program_metadata(course_id, serializer.data, request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProgramsListView(NelpCourseListView):
    """
    API view to list courses with program metadata.
    **Use Cases**
        - List courses with associated program metadata for request user
        - List courses filtered by national_id query parameter

    **Example Requests**
        GET /eox-nelp/api/programs/v1/program-lookup/
        GET /eox-nelp/api/programs/v1/program-lookup/?national_id=1234567890
    """
    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated, ProgramsLookupPermission]

    @require_national_id_query_param()
    def get(self, request, *args, **kwargs):
        """
        List courses with program metadata for the request user or filtered by national_id.
        Args:
            request: HTTP request object
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        Returns:
            Response with list of courses and their program metadata or error
        """
        course_api_list = super().get(request, *args, **kwargs).data["results"]

        program_lookup_list = []
        for course_api_data in course_api_list:
            program_lookup = get_program_lookup_representation(course_api_data)
            program_lookup_serializer = ProgramLookupSerializer(data=program_lookup)
            if program_lookup_serializer.is_valid():
                program_lookup_list.append(program_lookup_serializer.data)
            else:
                program_lookup_list.append(
                    {
                        "error": "Invalid program lookup data",
                        "details": program_lookup_serializer.errors,
                        "course_id": course_api_data.get("id"),
                    }
                )

        return Response(program_lookup_list, status=status.HTTP_200_OK)

    def get_queryset(self):
        """Override qs to query by national_id if provided.
        Also filter by enrolled courses only.
        Returns:
            List of enrolled courses for the user qs: Depending on performance this list queryset  could be improved to
            lazy sequence as used in
            https://github.com/openedx/edx-platform/blob/258f3fc/lms/djangoapps/course_api/api.py#L111

        """
        user = self.request.user
        if national_id := self.request.query_params.get("national_id"):
            user = get_object_or_404(User, extrainfo__national_id=national_id)
            visible_courses_qs = courses.get_courses(user=user)
        else:
            visible_courses_qs = super().get_queryset()
        enrolled_qs = [course for course in visible_courses_qs if CourseEnrollment.is_enrolled(user, str(course.id))]
        return enrolled_qs
