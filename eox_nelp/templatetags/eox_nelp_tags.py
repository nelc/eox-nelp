"""Template filters shared by the e-mail templates (and any Django template of a theme).

Usage: `{% load eox_nelp_tags %}` then `{{ course.effort|effort_hours }}`.
"""
from django import template

from eox_nelp.effort import format_effort_hours

register = template.Library()
register.filter("effort_hours", format_effort_hours)
