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

from eox_nelp.access import (
    ENFORCE_TENANT_SCOPED_LOOKUPS,
    evaluate_rule,
    get_tenant_orgs,
    has_global_lookup,
    is_tenant_member,
)
from eox_nelp.audit import CallerAuditMixin
from eox_nelp.certificates.api.v1.serializers import CertificateSerializer

GeneratedCertificate = get_generated_certificate()
User = get_user_model()


class UserCertificateListView(CallerAuditMixin, APIView):
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

    **Tenant scope**
        Once the waffle switch eox_nelp.enforce_tenant_scoped_lookups is on, a caller without global lookup
        (superuser or member of the eox_nelp_global_lookup group) only gets people who belong to the request tenant
        and certificates of the tenant's orgs; anything else answers as not found. While the switch is off the
        verdict is only logged.

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
    audit_surface = "certificates.v1.users"

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
        self.audit_extra["lookup_type"] = "certificate_id" if certificate_id else "national_id"

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

        self.audit_extra["target_user_id"] = user.id
        certificates = self.scope_to_tenant(request, user, certificates, by_certificate_id=bool(certificate_id))

        if certificates is None:
            # Out of the tenant: answer exactly like a lookup that matched nothing.
            error = (
                "Certificate with the provided certificate ID was not found." if certificate_id
                else "User with the provided national ID was not found."
            )
            return Response({"error": error}, status=status.HTTP_404_NOT_FOUND)

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

    def scope_to_tenant(self, request, user, certificates, by_certificate_id):
        """
        Apply the tenant-scope rule (eox_nelp.enforce_tenant_scoped_lookups) and record its verdict for the audit line.

        By certificate ID the certificate itself must belong to an org of the tenant; by national ID the person must
        be a member of the tenant, and only the certificates of the tenant's orgs are returned.

        Returns:
            The certificates to serialize, or None when the lookup must answer as not found.
        """
        if has_global_lookup(request.user):
            self.audit_extra["tenant_scope"] = "global"
            return certificates

        tenant_orgs = get_tenant_orgs()
        in_tenant = [certificate for certificate in certificates if certificate.course_id.org.lower() in tenant_orgs]
        self.audit_extra["certificates_outside_tenant"] = len(certificates) - len(in_tenant)
        allowed = bool(in_tenant) if by_certificate_id else is_tenant_member(user, getattr(request, "site", None))

        if evaluate_rule(ENFORCE_TENANT_SCOPED_LOOKUPS, "tenant_scope", allowed, self.audit_extra):
            return None

        return in_tenant if ENFORCE_TENANT_SCOPED_LOOKUPS.is_enabled() else certificates
