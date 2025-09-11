"""Programs API v1 URLs."""
from django.urls import re_path
from django.conf import settings

from eox_nelp.programs.api.v1.views import ProgramsMetadataView

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    re_path(fr'metadata/{settings.COURSE_KEY_PATTERN}$', ProgramsMetadataView.as_view(), name='programs-metadata'),
]
