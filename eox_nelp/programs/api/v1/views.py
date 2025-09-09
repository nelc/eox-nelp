"""Programs API v1 Views."""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.programs.api.v1.serializers import ProgramsMetadataSerializer


class ProgramsMetadataView(APIView):
    """
    API view for retrieving program metadata by course ID.

    **Use Cases**
        Retrieve metadata for a specific course program

    **Example Requests**
        GET /api/v1/programs/metadata/{course_id}/

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
        * 401 if authentication failed
        * 404 if course not found
    """

    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated]

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

    def _get_program_metadata(self, course_id):
        """
        Retrieve program metadata for a course.

        This is a mock implementation. In a real scenario, this would:
        1. Query the database for course information
        2. Fetch program details from external services
        3. Aggregate metadata from various sources

        Args:
            course_id: Course identifier

        Returns:
            dict: Program metadata or None if not found
        """
        # Mock data - replace with actual database/service calls
        mock_programs = {
            'course-v1:edX+DemoX+Demo_Course': {
                'trainer_type': 10,
                'Type_of_Activity': 155,
                'Mandatory': '01',
                'Program_ABROVE': '00',
                'Program_code': 'FX-TEACHER-101'
            },
            'course-v1:edX+CS101+2024': {
                'trainer_type': 10,
                'Type_of_Activity': 201,
                'Mandatory': '00',
                'Program_ABROVE': '01',
                'Program_code': 'CS-FUNDAMENTALS-2024'
            }
        }

        return mock_programs.get(course_id)
