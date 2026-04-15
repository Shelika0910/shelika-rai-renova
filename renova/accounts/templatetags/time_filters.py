from django import template
from django.utils import timezone
from django.utils.timesince import timesince
from datetime import timedelta

register = template.Library()


@register.filter
def time_ago(dt):
    """
    Return a human-readable time difference from now.
    Properly handles timezone-aware datetimes.
    """
    if not dt:
        return ""
    
    # Ensure we're working with timezone-aware datetime
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    now = timezone.now()
    return f"{timesince(dt, now)} ago"


@register.filter
def format_datetime_nice(dt, format_str="Y-m-d H:i"):
    """
    Format datetime in a user-friendly way.
    format_str follows Python's datetime format codes.
    """
    if not dt:
        return ""
    
    # Ensure we're working with timezone-aware datetime
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    # Convert to local timezone if needed
    dt = timezone.localtime(dt)
    
    return dt.strftime("%Y-%m-%d %H:%M")


@register.filter
def local_datetime(dt):
    """
    Convert UTC datetime to local timezone for display.
    """
    if not dt:
        return ""
    
    # Ensure we're working with timezone-aware datetime
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    # Convert to local timezone
    dt = timezone.localtime(dt)
    
    return dt.strftime("%Y-%m-%d %H:%M:%S")
