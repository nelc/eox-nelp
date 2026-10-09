"""Stats Views file.

Contains all the views for stats

classes:
    get_tenant_stats: function based view.
"""
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
    context = {
        query_param: "true" if request.GET.get(query_param, "true") == "true" else "false"
        for query_param in STATS_QUERY_PARAMS
    }

    return edxmako.shortcuts.render_to_response("tenant_stats/index.html", context, "main", request)
