"""Programs API v1 URLs."""
from django.urls import path

from eox_nelp.programs.api.v1.views import ProgramsMetadataView

app_name = "eox_nelp"  # pylint: disable=invalid-name

urlpatterns = [
    path('metadata/<str:course_id>/', ProgramsMetadataView.as_view(), name='programs-metadata'),
]
