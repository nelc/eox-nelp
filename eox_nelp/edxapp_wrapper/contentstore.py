"""
Wrapper cms.djangoapps.contentstore module.

This contains all the required dependencies from contentstore

Attributes:
    CourseAboutSearchIndexer: Wrapper CourseAboutSearchIndexer class.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_CONTENTSTORE)

CourseAboutSearchIndexer = backend.get_course_about_search_indexer()
