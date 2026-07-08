"""
URL configuration for the Certificates API.

This module routes API requests related to certificate management,
delegating version-specific endpoints to their respective modules.
"""
from django.urls import include, path

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    path("v1/", include("eox_nelp.certificates.api.v1.urls", namespace="v1")),
]
