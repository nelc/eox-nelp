"""Programs API v1 URLs."""

from django.conf import settings
from django.urls import path, re_path

from eox_nelp.programs.api.v1.views import ProgramsListView, ProgramsMetadataView

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    re_path(rf"metadata/{settings.COURSE_ID_PATTERN}/?$", ProgramsMetadataView.as_view(), name="programs-metadata"),
    path('program-lookup/', ProgramsListView.as_view(), name="program-lookup"),
]
