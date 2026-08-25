"""
Certificates API v1 URL configuration.

This module defines the v1 endpoints for certificate management.

Available routes:
- GET /users/<national_id>/: Retrieves all certificates for a
  user with the specified 10-digit national ID.
- GET /users/<certificate_id>/: Retrieves the single certificate matching the
  specified 32-character certificate ID (the GeneratedCertificate verify_uuid),
  together with its owner's details.
"""
from django.urls import re_path

from eox_nelp.certificates.api.v1 import views

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    re_path(
        r'^users/(?P<national_id>\d{10})/$',
        views.UserCertificateListView.as_view(),
        name='user-certificate-list',
    ),
    re_path(
        r'^users/(?P<certificate_id>[0-9a-fA-F]{32})/$',
        views.UserCertificateListView.as_view(),
        name='user-certificate-detail',
    ),
]
