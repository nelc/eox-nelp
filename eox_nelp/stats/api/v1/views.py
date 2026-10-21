"""Stats API v1 view file.

views:
    GeneralTenantStatsView: View that handles the general tenant stats.
    GeneralTenantCoursesView: View that handles the general courses stats.
"""
from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_nelp.access import TenantStaffOrLogOnly
from eox_nelp.audit import CallerAuditMixin
from eox_nelp.stats import metrics

User = get_user_model()


class GeneralTenantStatsView(CallerAuditMixin, APIView):
    """Class view. Handle general tenant stats.

    ## Usage
    The components key depends on the setting API_XBLOCK_TYPES, this should be
    a list of strings like the following

    ``` json
    [" problem", "video", "discussion"]
    ```

    ### **GET** /eox-nelp/api/stats/v1/tenant/

    **GET Response Values**
    ``` json
    {
        "learners": 1,
        "courses": 3,
        "instructors": 2,
        "components": {
            "discussion": 0,
            "drag-and-drop-v2": 0,
            "html": 133,
            "openassessment": 0,
            "problem": 49,
            "video": 0
        },
        "certiticates": {
            "downloadable": 5,
            "notpassing": 4
        }
    }
    ```
    """

    audit_surface = "stats.v1.tenant"
    # The project defaults stay first; the tenant-staff rule only logs until eox_nelp.enforce_stats_staff_only is on.
    permission_classes = [*APIView.permission_classes, TenantStaffOrLogOnly]

    def get(self, request):
        """Return general tenant stats."""
        tenant = request.site.domain
        courses = metrics.get_courses_metrics(tenant)
        components = {}
        certificates = {}
        for metric in courses.get("metrics", []):
            course_components = metric.get("components", {})
            certificates_components = metric.get("certificates", {}).get("total", {})

            for key, value in course_components.items():
                components[key] = components.get(key, 0) + value
            for key, value in certificates_components.items():
                certificates[key] = certificates.get(key, 0) + value

        return Response({
            "learners": metrics.get_learners_metric(tenant),
            "courses": courses.get("total_courses", 0),
            "instructors": metrics.get_instructors_metric(tenant),
            "components": components,
            "certificates": certificates,
        })


class GeneralCourseStatsView(CallerAuditMixin, APIView):
    """Class view that returns a list of course stats or a specific course stats.

    ## Usage
    The components key depends on the setting ALLOWED_VERTICAL_BLOCK_TYPES, this should be
    a list of strings like the following

    ``` json
    [" problem", "video", "discussion"]
    ```

    ### **GET** /eox-nelp/api/stats/v1/courses/

    **GET Response Values**
    ``` json
    {
        "total_courses": 4,
        "metrics": [
            {
                "id": "course-v1:patata+CS102+2023",
                "name": "PROCEDURAL SEDATION AND ANALGESIA COURSE",
                "learners": 0,
                "instructors": 1,
                "sections": 18,
                "sub_sections": 144,
                "units": 184,
                "components": {
                    "discussion": 0,
                    "drag-and-drop-v2": 0,
                    "html": 133,
                    "openassessment": 0,
                    "problem": 49,
                    "video": 0
                },
                "certificates" : {
                    "verified": {},
                    "honor": {},
                    "audit": {},
                    "professional": {},
                    "no-id-professional": {
                        "downloadable": 5,
                        "notpassing": 4,
                    },
                    "masters": {},
                    "executive-education": {},
                    "total": {
                        "downloadable": 5,
                        "notpassing": 4
                    }
                }
            },
            ...
        ]
    }
    ```

    ### **GET** /eox-nelp/api/stats/v1/courses/course-v1:potato+CS102+2023/

    **GET Response Values**
    ``` json
    {
        "id": "course-v1:potato+CS102+2023",
        "name": "PROCEDURAL SEDATION AND ANALGESIA COURSE",
        "learners": 0,
        "instructors": 1,
        "sections": 18,
        "sub_sections": 144,
        "units": 184,
        "components": {
            "discussion": 0,
            "drag-and-drop-v2": 0,
            "html": 133,
            "openassessment": 0,
            "problem": 49,
            "video": 0
        },
        "certificates" : {
            "verified": {...},
            "honor": {...},
            "audit": {...},
            "professional": {},
            "no-id-professional": {
                "downloadable": 5,
                "notpassing": 4...
            },
            "masters": {...},
            "executive-education": {...},
            "paid-executive-education": {...},
            "paid-bootcamp": {...},
            "total": {
                "downloadable": 5,
                "notpassing": 4
            }
        }
    }
    ```
    """

    audit_surface = "stats.v1.courses"
    permission_classes = [*APIView.permission_classes, TenantStaffOrLogOnly]

    def get(self, request, course_id=None):
        """Return general course stats."""
        tenant = request.site.domain

        if course_id:
            courses = metrics.get_cached_courses(tenant)
            course = courses.filter(id=course_id).first()

            if not course:
                raise Http404

            return Response(metrics.get_course_metrics(course.id))

        return Response(metrics.get_courses_metrics(tenant))
