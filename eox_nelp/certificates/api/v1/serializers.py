"""
Certificates API v1 serializers.

This module contains the serializers for the certificates API endpoints.
"""
from django.conf import settings
from eox_core.edxapp_wrapper.certificates import get_generated_certificate
from rest_framework import serializers

from eox_nelp.edxapp_wrapper.certificates import utils as certificates_utils
from eox_nelp.edxapp_wrapper.site_configuration import configuration_helpers
from eox_nelp.utils import get_course_from_id

GeneratedCertificate = get_generated_certificate()


class CertificateSerializer(serializers.ModelSerializer):
    """
    Serializer for the GeneratedCertificate model.

    Maps native database fields and computes additional required data
    such as the tenant name, course organization, and the absolute URL
    to view or download the certificate.
    """
    tenant = serializers.SerializerMethodField()
    org = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()

    class Meta:
        """Class to configure serializer with  model GeneratedCertificate"""
        model = GeneratedCertificate
        fields = [
            "tenant",
            "org",
            "course_id",
            "course_name",
            "status",
            "mode",
            "certificate_url",
        ]

    def get_tenant(self, instance):
        """
        Retrieve the tenant (site name) associated with the certificate.

        Args:
            instance (GeneratedCertificate): The current certificate instance.

        Returns:
            str: The site name configured for the course's organization.
        """
        return configuration_helpers.get_value_for_org(
            instance.course_id.org,
            "SITE_NAME",
            settings.SITE_NAME,
        )

    def get_org(self, instance):
        """
        Retrieve the organization associated with the course.

        Args:
            instance (GeneratedCertificate): The certificate instance.

        Returns:
            str: The organization identifier.
        """
        return str(instance.course_id.org)

    def get_certificate_url(self, instance):
        """
        Generate the URL to view or download the certificate.

        Args:
            instance (GeneratedCertificate): The certificate instance.

        Returns:
            str: The URL for the certificate.
        """
        certificate_path = certificates_utils.get_certificate_url(
            user_id=instance.user_id,
            course_id=instance.course_id,
            uuid=instance.verify_uuid,
        )
        tenant_url = configuration_helpers.get_value_for_org(
            instance.course_id.org,
            "LMS_ROOT_URL",
            settings.LMS_ROOT_URL,
        )

        # Ensure safe concatenation without double or missing slashes
        clean_tenant_url = tenant_url.rstrip('/')
        clean_path = certificate_path.lstrip('/')

        return f"{clean_tenant_url}/{clean_path}"

    def get_course_name(self, instance):
        """
        Retrieve the display name of the course.

        Args:
            instance (GeneratedCertificate): The certificate instance.

        Returns:
            str: The display name of the course, or None if not found.
        """
        course = get_course_from_id(str(instance.course_id))

        return course.get("display_name")
