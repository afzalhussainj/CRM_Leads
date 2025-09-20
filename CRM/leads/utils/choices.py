def get_lead_status_choices():
    from common.models import LeadStatus

    # Fetch distinct status values from LeadStatus model
    statuses = (
        LeadStatus.objects.all().values_list("name", flat=True).distinct()
    )
    return [(status, status) for status in statuses]



def get_lead_source_choices():


    from common.models import LeadSource

    # Fetch distinct source values from LeadSource model
    sources = (
        LeadSource.objects.all().values_list("source", flat=True).distinct()
    )
    return [(source, source) for source in sources]