"""Wrapper course modes.
This contains all the required dependencies from course modes.

Attributes:
    backend: Imported module by using the plugin settings.
    CourseMode: Wrapper of CourseMode model.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_COURSE_MODES_BACKEND)
CourseMode = backend.get_course_mode_model()
