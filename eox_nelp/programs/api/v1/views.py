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
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer] if getattr(settings, 'DEBUG', None) else [JSONRenderer]
    def get(self, request, course_key_string):
        """
        Retrieve program metadata for the specified course ID.

        Args:
            request: HTTP request object
            course_id: Course identifier

        Returns:
            Response with program metadata or error
        """
        try:
            program_metadata = get_program_metadata(course_key_string)

            if not program_metadata:
                return Response(
                    {'error': 'Program metadata not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = ProgramsMetadataSerializer(program_metadata)

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, course_key_string):
        """
        Create or update program metadata for the specified course ID.

        Args:
            request: HTTP request object containing program metadata
            course_id: Course identifier

        Returns:
            Response with updated program metadata or error
        """
        try:
            serializer = ProgramsMetadataSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Invalid data', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            update_program_metadata(course_key_string, serializer.validated_data, request.user)

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
