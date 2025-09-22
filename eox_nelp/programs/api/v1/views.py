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

from eox_nelp.edxapp_wrapper.course_api import CourseDetailSerializer, CourseListView
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


def process_national_id_query_param():
    """Decorator to check if national_id query parameter is valid if provided.
    If not provided, the view will proceed without filtering by national_id.
    Using the request user if not provided. Added to the request object the nid_user attribute.
    Returns  422 if invalid.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if national_id := self.request.query_params.get("national_id"):
                if not is_valid_national_id(national_id):
                    return Response(
                        {
                            "error": "INVALID_NATIONAL_ID",
                            "message": "national_id must be digits only and 10–15 characters."
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                setattr(request, 'nid_user', get_object_or_404(User, extrainfo__national_id=national_id))
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


class ProgramsListView(CourseListView):
    """
    API view to list courses with program metadata.
    **Use Cases**
        - List visible courses with associated program metadata for request user
        - List courses in which the user identified by national_id is enrolled, provided the requesting user has permission to view them.

    **Example Requests**
        GET /eox-nelp/api/programs/v1/program-lookup/
        GET /eox-nelp/api/programs/v1/program-lookup/?national_id=1234567890
    """
    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated, ProgramsLookupPermission]
    serializer_class = ProgramLookupSerializer

    @process_national_id_query_param()
    def get(self, request, *args, **kwargs):
        """Override get to apply some filtering and pre processing."""
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """Override qs to query by national_id if provided.
        Returns:
            QuerySet: queryset of courses depending on national_id presence.
            If national_id is provided, returns courses the user nid.
            If not provided, returns all courses visible to the request user.
        """
        if getattr(self.request, 'nid_user', None):
            return courses.get_courses(user=self.request.nid_user)
        return super().get_queryset() ##Visible user queryset

    def filter_queryset(self, queryset):
        """
        Filter the queryset by course enrolled if the national_id query param is present.
        Returns:
        List of enrolled courses for the user qs: Depending on performance this list queryset  could be improved to
        lazy sequence as used in
        https://github.com/openedx/edx-platform/blob/258f3fc/lms/djangoapps/course_api/api.py#L111
        """
        if getattr(self.request, 'nid_user', None):
            queryset = [course for course in queryset if CourseEnrollment.is_enrolled(self.request.nid_user, str(course.id))]

        program_queryset = []
        for course in queryset:
            course_data = CourseDetailSerializer(course, context={'request': self.request}).data
            program_lookup = get_program_lookup_representation(course_data)
            program_queryset.append(program_lookup)

        return program_queryset
