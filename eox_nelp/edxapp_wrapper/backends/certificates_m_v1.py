"""Backend for certificates module.
This file contains all the necessary certificates dependencies from
https://github.com/eduNEXT/edunext-platform/tree/master/lms/djangoapps/certificates
"""
from django.apps import apps
from django.contrib import admin
from lms.djangoapps import certificates  # pylint: disable=import-error


def get_generated_certificates_admin():
    """Allow to get the openedX GeneratedCertificateAdmin class.
    https://github.com/eduNEXT/edunext-platform/tree/master/lms/djangoapps/certificates/admin.py

    Returns:
        GeneratedCertificateAdmin class.
    """
    if apps.is_installed(certificates.models.__package__):
        return certificates.admin.GeneratedCertificateAdmin

    return admin.ModelAdmin


def get_generate_course_certificate_method():
    """Allow to get the generate_course_certificate method.
    https://github.com/nelc/edx-platform/blob/open-release/palm.nelp/lms/djangoapps/certificates/generation.py#L20

    Returns:
        generate_course_certificate method.
    """
    return certificates.generation.generate_course_certificate


def get_certificates_utils():
    """Allow to get the certificates utils module.
    https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/lms/djangoapps/certificates/utils.py

    Returns:
        certificates.utils module.
    """
    return certificates.utils
