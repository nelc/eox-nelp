import os

from tutor import hooks

print(os.environ["DOCKER_IMAGE_OPENEDX"])


hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        ("DOCKER_IMAGE_OPENEDX", os.environ["DOCKER_IMAGE_OPENEDX"]),
    ]
)
