"""Backend for contentstore cms app.

This file contains all the necessary dependencies from
https://github.com/nelc/edx-platform/tree/open-release/redwood.nelp/cms/djangoapps/contentstore
"""
from cms.djangoapps.contentstore.courseware_index import CourseAboutSearchIndexer


def get_course_about_search_indexer():
    """Allow to get CourseAboutSearchIndexer class from
    https://github.com/nelc/edx-platform/blob/open-release/redwood.nelp/cms/djangoapps/contentstore/courseware_index.py#L550

    Returns:
        CourseAboutSearchIndexer class.
    """
    return CourseAboutSearchIndexer
