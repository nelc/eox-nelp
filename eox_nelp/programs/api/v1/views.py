"""Programs API v1 Views."""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.edxapp_wrapper.modulestore import modulestore
from eox_nelp.programs.api.v1.serializers import ProgramsMetadataSerializer
from cms.djangoapps.models.settings.course_metadata import CourseMetadata
from opaque_keys.edx.keys import CourseKey
from common.djangoapps.util.json_request import JsonResponse
from rest_framework.parsers import JSONParser
from cms.djangoapps.contentstore.views.course import update_course_advanced_settings
from django.conf import settings
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer


class ProgramsMetadataView(APIView):
    """
    API view for retrieving and updating program metadata by course ID.

    **Use Cases**
        - Retrieve metadata for a specific course program
        - Create or update program metadata for a course

    **Example Requests**
        GET /api/v1/programs/metadata/{course_id}/
        POST /api/v1/programs/metadata/{course_id}/

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
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer] if getattr(settings, 'DEBUG', None) else [JSONRenderer]
    def get(self, request, course_id):
        """
        Retrieve program metadata for the specified course ID.

        Args:
            request: HTTP request object
            course_id: Course identifier

        Returns:
            Response with program metadata or error
        """
        try:
            # Validate course_id format (basic validation)
            if not course_id or len(course_id.strip()) == 0:
                return Response(
                    {'error': 'Invalid course ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mock data - in a real implementation, this would fetch from database
            # or external service based on the course_id
            program_metadata = self._get_program_metadata(course_id)
            # return JsonResponse(program_metadata, status=status.HTTP_200_OK)
            if not program_metadata:
                return Response(
                    {'error': 'Program metadata not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Serialize the data
            serializer = ProgramsMetadataSerializer(program_metadata)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, course_id):
        """
        Create or update program metadata for the specified course ID.

        Args:
            request: HTTP request object containing program metadata
            course_id: Course identifier

        Returns:
            Response with updated program metadata or error
        """
        try:
            # Validate course_id format
            if not course_id or len(course_id.strip()) == 0:
                return Response(
                    {'error': 'Invalid course ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Parse and validate request data
            serializer = ProgramsMetadataSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update program metadata
            success = self._update_program_metadata(course_id, serializer.validated_data, request.user)

            if not success:
                return Response(
                    {'error': 'Failed to update program metadata'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(
                {'message': 'Program metadata updated successfully', 'data': serializer.data},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_program_metadata(self, course_id):
        """
        Retrieve program metadata for a course.


        Args:
            course_id: Course identifier

        Returns:
            dict: Program metadata or None if not found
        """
        # Mock data - replace with actual database/service calls
        course_key = CourseKey.from_string(course_id)
        course_block = modulestore().get_course(course_key, depth=0)
        course_metadata = CourseMetadata.fetch(course_block)
        program_metadata = course_metadata.get("other_course_settings", {}).get("value", {}).get("program_metadata_v1", {})
        return program_metadata

    def _update_program_metadata(self, course_id, program_data, user):
        """
        Update program metadata for a course.

        Args:
            course_id: Course identifier
            program_data: Dictionary containing program metadata to update
            user: User object for the update operation

        Returns:
            bool: True if update was successful, False otherwise
        """
        course_key = CourseKey.from_string(course_id)
        course_block = modulestore().get_course(course_key, depth=0)
        course_metadata = CourseMetadata.fetch(course_block)
        other_course_settings = course_metadata.get("other_course_settings", {})
        other_course_settings_value = other_course_settings.get("value", {})
        other_course_settings_value["program_metadata_v1"] = program_data
        other_course_settings["value"] = other_course_settings_value
        updated_data = update_course_advanced_settings(
            course_block,
            {"other_course_settings": other_course_settings},
            user,
        )
        return updated_data["other_course_settings"]["value"]["program_metadata_v1"]
