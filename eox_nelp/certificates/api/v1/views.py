"""
Certificates API v1 views.

This module contains the views responsible for handling API requests
related to user certificates.
"""
from django.contrib.auth import get_user_model
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.certificates.api.v1.serializers import CertificateSerializer

GeneratedCertificate = get_generated_certificate()
User = get_user_model()


class UserCertificateListView(APIView):
    """
    API view for retrieving user certificates by national ID.

    **Use Cases**
        - Retrieve a list of generated certificates for a specific user using their national ID

    **Example Requests**
        GET /eox-nelp/api/certificates/v1/users/1234567890/

    **Authentication**
        Requires JWT token or session authentication.
        User must have staff or superadmin privileges.

    **Response Values**
        Returns user information and a list of their certificates including:
        - username: The username of the user (string)
        - national_id: The 10-digit national identification number (string)
        - certificates: A list of certificate objects containing:
            - tenant: The site name configured for the course's organization (string)
            - org: The organization identifier (string)
            - course_id: The course identifier (string)
            - status: The generation status of the certificate (string)
            - mode: The enrollment mode (string)
            - certificate_url: The absolute URL to view or download the certificate (string)

    **Returns**
        * 200 on success with the user's certificates data
        * 401 if authentication failed
        * 403 if the user does not have permission (not staff/superadmin)
        * 404 if the user with the provided national ID is not found
    """
    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, national_id, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Retrieve certificates for a given national ID.

        Args:
            request (Request): The incoming HTTP request object.
            national_id (str): A 10-digit string representing the user's national ID.

        Returns:
            Response: A DRF Response object with a success message and HTTP 200 status,
                      or HTTP 404 status if the user is not found.
        """
        user = User.objects.filter(extrainfo__national_id=national_id).first()

        if not user:
            return Response(
                {"error": "User with the provided national ID was not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        certificates = GeneratedCertificate.objects.filter(user=user)
        serializer = CertificateSerializer(certificates, many=True, context={'request': request})

        response_data = {
            "username": user.username,
            "national_id": national_id,
            "certificates": serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)
