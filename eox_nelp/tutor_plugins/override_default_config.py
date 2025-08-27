"""
override_default_config.py

This module is a Tutor plugin extension that leverages the
`tutor.hooks.Filters.CONFIG_OVERRIDES` filter to override default
configuration values used by the Open edX platform within Tutor.

Purpose:
--------
The goal of this module is to provide a centralized and explicit way to
modify existing configuration settings, either from Tutor core or other
plugins. By registering override values through the `CONFIG_OVERRIDES`
filter, users can adjust environment variables or configuration
parameters that affect the behavior of the LMS, CMS, or supporting
services.

How It Works:
-------------
- `CONFIG_OVERRIDES` accepts a list of `(name, value)` tuples.
- Each tuple specifies the setting to override and its new value.
- Overrides are applied at runtime and take precedence over defaults
  defined in Tutor or other plugins.

Notes:
------
- Use overrides carefully: critical settings (e.g., passwords, secrets)
  should not be modified without a clear migration path.
- While this module currently overrides only the `DOCKER_IMAGE_OPENEDX`
  setting (to control which Docker image is used by Open edX services),
  it can be extended to override additional configuration values in a
  consistent way.

Example:
--------
    hooks.Filters.CONFIG_OVERRIDES.add_items(
        [
            ("DOCKER_IMAGE_OPENEDX", os.environ["DOCKER_IMAGE_OPENEDX"]),
        ]
    )

References:
-----------
Tutor Documentation: CONFIG_OVERRIDES Filter
https://docs.tutor.overhang.io/
"""
import os

from tutor import hooks

hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        ("DOCKER_IMAGE_OPENEDX", os.environ["DOCKER_IMAGE_OPENEDX"]),
    ]
)
