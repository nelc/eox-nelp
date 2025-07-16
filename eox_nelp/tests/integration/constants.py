"""
This module centralizes common variables used in integration testing environments.
Its purpose is to avoid duplication of constant values (such as base URLs) and to enable
dynamic configuration through environment variables.
"""
import os

LMS_BASE_URL = f"http://{os.environ.get('LMS_HOST', 'local.edly.io')}"
