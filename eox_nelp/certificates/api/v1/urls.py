"""
Certificates API v1 URL configuration.

This module defines the v1 endpoints for certificate management.

Available routes:
- GET /users/<national_id>/: Retrieves all certificates for a
  user with the specified 10-digit national ID.
"""
from django.urls import re_path

from eox_nelp.certificates.api.v1 import views

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    re_path(
        r'^users/(?P<national_id>\d{10})/$',
        views.UserCertificateListView.as_view(),
        name='user-certificate-list',
    )
]
