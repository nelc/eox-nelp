"""URLs of the enrollment API override (mounted at eox-core/api/v1/enrollment/)."""
from django.urls import re_path

from eox_nelp.enrollment_api.views import NelpEdxappEnrollment

app_name = 'eox_nelp_enrollment_api'  # pylint: disable=invalid-name

urlpatterns = [
    re_path(r'^$', NelpEdxappEnrollment.as_view(), name='edxapp-enrollment'),
]
