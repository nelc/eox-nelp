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
    API view for retrieving certificates by national ID or by certificate ID.

    **Use Cases**
        - Retrieve a list of generated certificates for a specific user using their national ID
        - Retrieve a single certificate, and its owner's details, using the certificate ID

    **Example Requests**
        GET /eox-nelp/api/certificates/v1/users/1234567890/
        GET /eox-nelp/api/certificates/v1/users/2c97649425bb49189470f05bf7d98c1a/

        The lookup key is taken from the path. A 10-digit value is read as a national ID and
        returns every certificate of that user; a 32-character hexadecimal value is read as a
        certificate ID (the GeneratedCertificate verify_uuid) and returns only that certificate.

    **Authentication**
        Requires JWT token or session authentication.
        User must have staff or superadmin privileges.

    **Response Values**
        Returns user information and a list of their certificates including:
        - username: The username of the user (string)
        - national_id: The 10-digit national identification number (string)
        - english_name: The user's full name as stored in their profile (string)
        - arabic_name: The user's full name in Arabic (string)
        - certificates: A list of certificate objects containing:
            - certificate_id: The certificate identifier, also used to verify it (string)
            - tenant: The site name configured for the course's organization (string)
            - org: The organization identifier (string)
            - course_id: The course identifier (string)
            - course_name: The display name of the course (string)
            - status: The generation status of the certificate (string)
            - mode: The enrollment mode (string)
            - issue_date: The ISO 8601 date the certificate was issued (string)
            - certificate_url: The absolute URL to view or download the certificate (string)

    **Returns**
        * 200 on success with the user's certificates data
        * 401 if authentication failed
        * 403 if the user does not have permission (not staff/superadmin)
        * 404 if no user matches the provided national ID, or no certificate matches the
          provided certificate ID
    """
    authentication_classes = [JwtAuthentication, SessionAuthenticationAllowInactiveUser]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, national_id=None, certificate_id=None, **kwargs):  # pylint: disable=unused-argument
        """
        Retrieve certificates for a given national ID or certificate ID.

        Exactly one of the lookup keys is set, since each one is bound to its own url pattern.

        Args:
            request (Request): The incoming HTTP request object.
            national_id (str): A 10-digit string representing the user's national ID.
            certificate_id (str): A 32-character string representing the certificate verify_uuid.

        Returns:
            Response: A DRF Response object with the owner's details and their certificates and
                      HTTP 200 status, or HTTP 404 status if the lookup key matches no record.
        """
        if certificate_id:
            certificate = GeneratedCertificate.objects.filter(
                verify_uuid=certificate_id,
            ).select_related("user").first()

            if not certificate:
                return Response(
                    {"error": "Certificate with the provided certificate ID was not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            user = certificate.user
            certificates = [certificate]
        else:
            user = User.objects.filter(extrainfo__national_id=national_id).first()

            if not user:
                return Response(
                    {"error": "User with the provided national ID was not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            certificates = GeneratedCertificate.objects.filter(user=user)

        serializer = CertificateSerializer(certificates, many=True, context={'request': request})
        extra_info = getattr(user, "extrainfo", None)
        profile = getattr(user, "profile", None)

        response_data = {
            "username": user.username,
            "national_id": getattr(extra_info, "national_id", None),
            "english_name": getattr(profile, "name", None),
            "arabic_name": getattr(extra_info, "arabic_name", None),
            "certificates": serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
