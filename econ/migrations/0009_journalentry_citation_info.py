from django.db import migrations, models


JOURNAL_METADATA = [
    {
        "title": "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective",
        "journal_url": "https://www.sciencedirect.com/science/article/pii/S2667091723000031",
        "citation_info": "Vol. 3 | DOI: 10.1016/j.urbmob.2023.100047",
    },
    {
        "title": "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis",
        "journal_url": "https://www.sciencedirect.com/science/article/abs/pii/S0966692323002636",
        "citation_info": "Vol. 115 | DOI: 10.1016/j.jtrangeo.2023.103791",
    },
    {
        "title": "The Association between Urban Public Transport Infrastructure and Social Equity and Spatial Accessibility within the Urban Environment: An Investigation of Tramlink in London",
        "journal_url": "https://www.mdpi.com/2071-1050/11/5/1229",
        "citation_info": "Vol. 11(5) | Art. 1229 | DOI: 10.3390/su11051229",
    },
    {
        "title": "Governing urban accessibility: moving beyond transport and mobility",
        "journal_url": "https://www.tandfonline.com/doi/abs/10.1080/23800127.2018.1438149",
        "citation_info": "Vol. 3(1) | pp. 8-33 | DOI: 10.1080/23800127.2018.1438149",
    },
    {
        "title": "The role of railway in handling transport services of cities and agglomerations",
        "journal_url": "https://www.sciencedirect.com/science/article/pii/S2352146519301310",
        "citation_info": "Vol. 39 | pp. 405-416 | DOI: 10.1016/j.trpro.2019.06.043",
    },
]


def seed_citation_info(apps, schema_editor):
    JournalEntry = apps.get_model("econ", "JournalEntry")

    for entry in JOURNAL_METADATA:
        JournalEntry.objects.filter(
            title=entry["title"],
            journal_url=entry["journal_url"],
        ).update(citation_info=entry["citation_info"])


def unseed_citation_info(apps, schema_editor):
    JournalEntry = apps.get_model("econ", "JournalEntry")
    JournalEntry.objects.filter(title__in=[entry["title"] for entry in JOURNAL_METADATA]).update(citation_info="")


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0008_journalentry_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="journalentry",
            name="citation_info",
            field=models.CharField(blank=True, default="", max_length=300),
            preserve_default=False,
        ),
        migrations.RunPython(seed_citation_info, unseed_citation_info),
    ]
