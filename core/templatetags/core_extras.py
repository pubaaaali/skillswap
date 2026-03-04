"""Custom template tags and filters for SkillSwap."""

from django import template

register = template.Library()


@register.filter
def abs_value(value):
    """Return the absolute value of a number."""
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value


@register.filter
def star_range(rating):
    """Return a range for rendering star icons (1..rating)."""
    try:
        return range(1, int(rating) + 1)
    except (TypeError, ValueError):
        return range(0)


@register.filter
def empty_stars(rating, max_stars=5):
    """Return range for empty stars."""
    try:
        return range(int(rating) + 1, max_stars + 1)
    except (TypeError, ValueError):
        return range(0)


@register.simple_tag
def hours_display(hours):
    """Format hours as e.g. '1.0h' or '2.5h'."""
    try:
        return f"{hours:.1f}h"
    except (TypeError, ValueError):
        return f"{hours}h"
