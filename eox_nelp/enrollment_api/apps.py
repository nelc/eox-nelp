"""Second eox-nelp plugin app: takes over the eox-core enrollment URL.

It is a separate app (own label, own entry point) only because a plugin has ONE url_config
and eox_nelp's is already `^eox-nelp/`. Plugin URL order is whatever stevedore yields, not a
contract, so `tests/integration/test_enrollment_url_takeover.py` must pass in the built image.
If it ever fails, the decided fallback (a2-url-takeover) is to replace the eox-core view class
from `ready()`.
"""
from django.apps import AppConfig


class EnrollmentApiConfig(AppConfig):
    """Plugin app that serves POST /eox-core/api/v1/enrollment/ with the eox-nelp view."""

    name = 'eox_nelp.enrollment_api'
    label = 'eox_nelp_enrollment_api'
    verbose_name = 'Nelp enrollment API override'
    plugin_app = {
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'eox-nelp-enrollment-api',
                # Prefix only: urls.py matches the empty remainder, so exactly this URL is taken
                # and no unrelated eox-core route is shadowed.
                'regex': r'^eox-core/api/v1/enrollment/',
                'relative_path': 'urls',
            },
        },
    }
