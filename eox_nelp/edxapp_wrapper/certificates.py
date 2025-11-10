"""Wrapper certificates module file.
This contains all the required dependencies from certificates.

Attributes:
    backend:Imported module by using the plugin settings.
    GeneratedCertificateAdmin: Wrapper GeneratedCertificateAdmin class.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_CERTIFICATES_BACKEND)

GeneratedCertificateAdmin = backend.get_generated_certificates_admin()
generate_course_certificate = backend.get_generate_course_certificate_method()
utils = backend.get_certificates_utils()
models = backend.get_certificates_models()
