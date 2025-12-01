def get_lead_status_choices():
    from django.core.cache import cache
    from common.models import LeadStatus

    # Cache for 1 hour (3600 seconds)
    cache_key = 'lead_status_choices'
    choices = cache.get(cache_key)
    
    if choices is None:
        # Fetch distinct status values from LeadStatus model
        statuses = (
            LeadStatus.objects.all().values_list("name", flat=True).distinct()
        )
        choices = [(status, status) for status in statuses]
        cache.set(cache_key, choices, 3600)  # Cache for 1 hour
    
    return choices


def get_lead_source_choices():
    from django.core.cache import cache
    from common.models import LeadSource

    # Cache for 1 hour (3600 seconds)
    cache_key = 'lead_source_choices'
    choices = cache.get(cache_key)
    
    if choices is None:
        # Fetch distinct source values from LeadSource model
        sources = (
            LeadSource.objects.all().values_list("source", flat=True).distinct()
        )
        choices = [(source, source) for source in sources]
        cache.set(cache_key, choices, 3600)  # Cache for 1 hour
    
    return choices