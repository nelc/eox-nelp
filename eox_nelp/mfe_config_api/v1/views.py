"""The generic views for MFE_CONFIG API. Nelp flavour."""

import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from eox_theming.configuration import ThemingConfiguration as theming
from rest_framework import status

from eox_nelp.edxapp_wrapper.mfe_config_view import MFEConfigView


class NelpMFEConfigView(MFEConfigView):
    """
    Provides an API endpoint to get the MFE_CONFIG from site configuration with
    nelp extra fields.
    Based on https://github.com/openedx/edx-platform/blob/master/lms/djangoapps/mfe_config_api/views.py.
    Added MFE_CONFIG_MAP functionality.
    eg. in django settings:
    "MFE_CONFIG_MAP": {
        "favicon_path": "FAVICON_URL",
        "logo_image_url": "LOGO_URL"
    }

    **Usage**
    Get common config:
    GET eox-nelp/api/mfe_config/v1
    **GET Response Values**
    ```
    {
        "BASE_URL": "https://name_of_mfe.example.com",
        "LANGUAGE_PREFERENCE_COOKIE_NAME": "example-language-preference",
        "CREDENTIALS_BASE_URL": "https://credentials.example.com",
        "DISCOVERY_API_BASE_URL": "https://discovery.example.com",
        "LMS_BASE_URL": "https://courses.example.com",
        "LOGIN_URL": "https://courses.example.com/login",
        "LOGOUT_URL": "https://courses.example.com/logout",
        "STUDIO_BASE_URL": "https://studio.example.com",
        "THEME_OPTIONS": {"CONTROL_THEME_OPTIONS": "values"...}
        "CUSTOM_PRIMARY_COLORS": {"pgn-color-primary-base": "interactive_color"}
        .. and other django setting or tenant config vars mapped with MFE_CONFIG_MAP..
        "FAVICON_URL": "settings_favicon_path_value"
        "LOGO_URL": "settings_logo_image_url_value"
        ...
    }
    ```
    """
    @method_decorator(cache_page(settings.EOX_NELP_MFE_CONFIG_API_CACHE_TIMEOUT))
    def get(self, request):
        """
        Return the MFE configuration by NELP(adding custom nelp fields).
        """
        base_get_response = super().get(request)

        if base_get_response.status_code != 200:
            return base_get_response

        mfe_config_dict = json.loads(base_get_response.content)
        theme_options = theming.options('THEME_OPTIONS')
        interactive_color = theming.options('interactive_color')
        theme_additions = {
            'THEME_OPTIONS': theme_options,
            'CUSTOM_PRIMARY_COLORS': {'pgn-color-primary-base': interactive_color},
        }
        mfe_config_dict.update(theme_additions)

        mfe_config_map = getattr(settings, "MFE_CONFIG_MAP", {})
        mfe_config_map_additions = {
            mfe_config_key: getattr(settings, setting_key, None)
            for (setting_key, mfe_config_key) in mfe_config_map.items()
        }
        mfe_config_dict.update(mfe_config_map_additions)

        return JsonResponse(mfe_config_dict, status=status.HTTP_200_OK)
