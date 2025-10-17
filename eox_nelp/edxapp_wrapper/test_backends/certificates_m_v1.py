"""Test backend for certificates module."""
from django.contrib.auth.models import User
from django.db import models
from mock import Mock
from model_utils import Choices
from opaque_keys.edx.django.models import CourseKeyField

from eox_nelp.edxapp_wrapper.test_backends import create_test_model


def get_generated_certificates_admin():
    """Return test admin class.
    Returns:
        Mock class.
    """
    return Mock()


MODES = Choices(
    'verified',
    'honor',
    'audit',
    'professional',
    'no-id-professional',
    'masters',
    'executive-education',
    'paid-executive-education',
    'paid-bootcamp',
)


def get_generated_certificate():
    """Return test model.
    Returns:
        Generated Certificates  dummy model.
    """
    generated_certificate_fields = {
        "user": models.ForeignKey(User, on_delete=models.CASCADE),
        "course_id": CourseKeyField(max_length=255, blank=True, default=None),
        "grade": models.CharField(max_length=5, blank=True, default=''),
        "status": models.CharField(max_length=32, default='unavailable'),
        "mode": models.CharField(max_length=32, choices=MODES, default=MODES.honor),
        # not model fields :
        "MODES": MODES,
    }

    return create_test_model(
        "GeneratedCertificate", "eox_nelp", __package__, generated_certificate_fields
    )


def get_generate_course_certificate_method():
    """Return generate_course_certificate mock method.

    Returns:
        Mock instance.
    """
    return Mock()


def get_certificates_utils():
    """Return utils mock module
    Returns:
         Mock instance.
    """
    return Mock()
