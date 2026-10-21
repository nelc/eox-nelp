"""Stats Views file.

Contains all the views for stats

classes:
    get_tenant_stats: function based view.
"""
from django.core.exceptions import PermissionDenied

from eox_nelp.access import ENFORCE_STATS_STAFF_ONLY, evaluate_rule, is_tenant_staff
from eox_nelp.audit import log_api_caller
from eox_nelp.edxapp_wrapper.edxmako import edxmako

STATS_QUERY_PARAMS = [
    "show_courses",
    "show_videos",
    "show_problems",
    "show_learners",
    "show_instructors",
    "show_certificates",
]


def get_tenant_stats(request):
    """
    Simple function based view that renders the StatsContainer essential component.
    By default this will show all the available stats.

    Examples:
        renders all available stats /eox-nelp/stats/tenant/

        filters out videos, courses and instructors
        /eox-nelp/stats/tenant/?show_videos=false&show_courses=false&show_instructors=false

    The available options are:

        |       name       | default |         Description         |

        |    show_videos   |   true  |    Show the videos stats    |

        |   show_courses   |   true  |    Show the courses stats   |

        |   show_learners  |   true  |    Show the learner stats   |

        | show_instructors |   true  |  Show the instructors stats |

        |  show_problems   |   true  |   Show the problems stats   |

        | show_certificates|   true  | Show the certificates stats |
    """
    # Only the known flags are read, and each is coerced to a strict "true"/"false"
    # string. This preserves the template's existing semantics (a stat is shown only
    # when its flag is exactly "true", the default) while keeping attacker-controlled
    # query values out of the rendered page: the context can never hold a reflected
    # string, so the flags can no longer be used as a reflected-XSS sink.
    audit_extra = {}
    allowed = is_tenant_staff(getattr(request, "user", None))
    if evaluate_rule(ENFORCE_STATS_STAFF_ONLY, "stats_staff_only", allowed, audit_extra):
        log_api_caller(request, "stats.tenant_page", status=403, **audit_extra)
        raise PermissionDenied

    context = {
        query_param: "true" if request.GET.get(query_param, "true") == "true" else "false"
        for query_param in STATS_QUERY_PARAMS
    }

    response = edxmako.shortcuts.render_to_response("tenant_stats/index.html", context, "main", request)
    log_api_caller(request, "stats.tenant_page", status=response.status_code, **audit_extra)

    return response
