"""Programs API v1 Views."""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.programs.api.v1.serializers import ProgramsMetadataSerializer
from eox_nelp.programs.api.v1.utils import get_program_metadata, update_program_metadata
from django.conf import settings
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer


class ProgramsMetadataView(APIView):
    """
    API view for retrieving and updating program metadata by course ID.

    **Use Cases**
        - Retrieve metadata for a specific course program
        - Create or update program metadata for a course

    **Example Requests**
        GET /eox-nelp/api/programs/v1/metadata/course-v1:edx+cd101+23213/
        POST /eox-nelp/api/programs/v1/metadata/course-v1:edx+cd101+23213/

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
            program_metadata = get_program_metadata(course_id)
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

            program_metadata = update_program_metadata(course_id, serializer.validated_data, request.user)

            if not program_metadata:
                return Response(
                    {'error': 'Failed to update program metadata'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(
                program_metadata,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
